"""TShark live capture sensor — subprocess management.

Refactored to use the central TShark locator, safe command builder, and a
pluggable runner interface (RealTsharkRunner / MockTsharkRunner).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from typing import Callable, Optional

from netwatch.live.config import (
    TSHARK_BPF_FILTER,
    TSHARK_OUTPUT_FORMAT,
    TSHARK_PROMISCUOUS,
    TSHARK_SNAPLEN,
    LIVE_MAX_EVENT_QUEUE,
    LIVE_EVENTS_PER_SECOND_LOG,
)
from netwatch.live.tshark_command import (
    _validate_interface as _validate_interface_impl,
    build_live_capture_command,
)
from netwatch.live.tshark_locator import locate_tshark, validate_tshark
from netwatch.live.tshark_runner import RealTsharkRunner, TsharkRunner

logger = logging.getLogger(__name__)


# Backward-compat re-export (tests import this name from tshark_sensor)
def _validate_interface(iface: str) -> str:
    return _validate_interface_impl(iface)


class TSharkSensor:
    """Manages a TShark subprocess for live packet capture.

    Produces JSON lines (one per packet) via a callback or internal queue.
    """

    def __init__(self, runner: Optional[TsharkRunner] = None):
        self._runner = runner or RealTsharkRunner()
        self._process: Optional[object] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._callback: Optional[Callable[[dict], None]] = None
        self._queue: deque = deque(maxlen=LIVE_MAX_EVENT_QUEUE)
        self._stats = {
            "packets_captured": 0,
            "packets_received": 0,
            "packets_dropped": 0,
            "bytes_captured": 0,
            "start_time": None,
            "error": None,
            "exit_code": None,
        }
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return (
            self._running
            and self._process is not None
            and getattr(self._process, "poll", lambda: None)() is None
        )

    @property
    def stats(self) -> dict:
        with self._lock:
            return dict(self._stats)

    def _resolve_executable(self) -> Optional[str]:
        """Resolve TShark executable: config hint -> locator auto-discovery."""
        from netwatch.live.config import TSHARK_PATH

        hint = (TSHARK_PATH or "").strip()
        if hint:
            resolved = locate_tshark(hint)
            if resolved:
                return resolved
        # No config hint or hint failed -> auto-discover
        return locate_tshark("")

    def start(
        self,
        interface: str,
        callback: Optional[Callable[[dict], None]] = None,
        bpf_filter: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> bool:
        """Start TShark capture on the given interface.

        callback: called with parsed JSON dict for each packet line.
        Returns True if started successfully.
        """
        if self.is_running:
            logger.warning("TShark already running — stopping first")
            self.stop()

        iface = _validate_interface(interface)
        fmt = output_format or TSHARK_OUTPUT_FORMAT
        bf = bpf_filter or TSHARK_BPF_FILTER
        snaplen = str(TSHARK_SNAPLEN)

        exe = self._resolve_executable()
        if not exe:
            with self._lock:
                self._stats["error"] = (
                    "TShark executable not found. "
                    "Run scripts/check_tshark.py or scripts/setup.py to install and configure TShark."
                )
            logger.error("TShark executable not found (config hint: %r)", TSHARK_PATH)
            return False

        try:
            cmd = build_live_capture_command(
                executable=exe,
                interface=iface,
                output_format=fmt,
                bpf_filter=bf,
                snaplen=int(snaplen),
                promiscuous=TSHARK_PROMISCUOUS,
            )
        except ValueError as e:
            with self._lock:
                self._stats["error"] = f"Invalid TShark arguments: {e}"
            logger.error("Invalid TShark command arguments: %s", e)
            return False

        logger.info("Starting TShark: %s", " ".join(cmd))
        with self._lock:
            self._stats = {
                "packets_captured": 0,
                "packets_received": 0,
                "packets_dropped": 0,
                "bytes_captured": 0,
                "start_time": time.time(),
                "error": None,
                "exit_code": None,
            }

        try:
            self._process = self._runner.launch(cmd)
        except FileNotFoundError:
            with self._lock:
                self._stats["error"] = "TShark executable not found at resolved path"
            logger.error("TShark executable not found at: %s", exe)
            return False
        except PermissionError:
            with self._lock:
                self._stats["error"] = "Permission denied — need root or CAP_NET_RAW"
            logger.error("Permission denied starting TShark")
            return False
        except OSError as e:
            with self._lock:
                self._stats["error"] = f"OS error: {e}"
            logger.error("OS error starting TShark: %s", e)
            return False

        self._callback = callback
        self._running = True
        self._thread = threading.Thread(
            target=self._reader_loop,
            name="tshark-reader",
            daemon=True,
        )
        self._thread.start()
        logger.info("TShark started on %s", iface)
        return True

    def stop(self) -> dict:
        """Stop TShark and return final stats."""
        self._running = False
        stats = {}
        with self._lock:
            if self._process and getattr(self._process, "poll", lambda: None)() is None:
                try:
                    self._runner.terminate(self._process)
                except Exception:  # noqa: BLE001
                    pass
            if self._process:
                stats["exit_code"] = getattr(self._process, "returncode", None)
                self._stats["exit_code"] = getattr(self._process, "returncode", None)
                self._process = None
            stats.update(self._stats)
            self._stats["error"] = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        self._callback = None
        logger.info("TShark stopped. Stats: %s", stats)
        return stats

    def _reader_loop(self):
        """Read stdout lines from TShark and dispatch to callback."""
        if not self._process or not getattr(self._process, "stdout", None):
            return
        line_count = 0
        last_log = time.time()
        try:
            for line in self._process.stdout:
                if not self._running:
                    break
                line = line.strip()
                if not line:
                    continue
                line_count += 1
                with self._lock:
                    self._stats["packets_captured"] += 1
                parsed = None
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Non-JSON TShark line: %s", line[:80])
                    continue
                if self._callback:
                    try:
                        self._callback(parsed)
                    except Exception as e:  # noqa: BLE001
                        logger.warning("Callback error: %s", e)
                else:
                    self._queue.append(parsed)
                now = time.time()
                if now - last_log >= LIVE_EVENTS_PER_SECOND_LOG:
                    with self._lock:
                        elapsed = now - (self._stats.get("start_time") or now)
                        rate = self._stats["packets_captured"] / max(elapsed, 0.001)
                    logger.debug("TShark rate: %.0f pkts/sec", rate)
                    last_log = now
        except Exception as e:  # noqa: BLE001
            logger.error("TShark reader error: %s", e)
            with self._lock:
                self._stats["error"] = str(e)
        finally:
            self._running = False
            if self._process:
                stderr_data = ""
                try:
                    stderr_data = (
                        self._process.stderr.read(4096) if getattr(self._process, "stderr", None) else ""
                    )
                except Exception:
                    pass
                if stderr_data:
                    with self._lock:
                        self._stats["error"] = stderr_data.strip()[:500]

    def pop_events(self, max_n: int = 500) -> list:
        """Pop up to max_n events from the internal queue."""
        events = []
        while len(events) < max_n and self._queue:
            try:
                events.append(self._queue.popleft())
            except IndexError:
                break
        return events

    def check_alive(self) -> Optional[str]:
        """Return error message if process died, else None."""
        if not self._running:
            return "TShark is not running"
        if self._process and getattr(self._process, "poll", lambda: None)() is not None:
            code = getattr(self._process, "returncode", None)
            with self._lock:
                err = self._stats.get("error", "")
            return f"TShark exited with code {code}: {err}"
        return None