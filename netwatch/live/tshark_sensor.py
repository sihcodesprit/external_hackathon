"""TShark live capture sensor — subprocess management."""

import json
import logging
import os
import subprocess
import threading
import time
from collections import deque
from typing import Callable, Optional

from netwatch.live.config import (
    TSHARK_BPF_FILTER,
    TSHARK_OUTPUT_FORMAT,
    TSHARK_PATH,
    TSHARK_PROMISCUOUS,
    TSHARK_SNAPLEN,
    LIVE_MAX_EVENT_QUEUE,
    LIVE_EVENTS_PER_SECOND_LOG,
)

logger = logging.getLogger(__name__)

# Safe interface name validation: only alphanumeric, hyphens, underscores, dots
_VALID_IFACE_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")


def _validate_interface(iface: str) -> str:
    """Validate and return interface name, raise ValueError if invalid."""
    if not iface or not isinstance(iface, str):
        raise ValueError("Interface name is required")
    if not all(c in _VALID_IFACE_CHARS for c in iface):
        raise ValueError(f"Invalid interface name: {iface!r}")
    if len(iface) > 255:
        raise ValueError("Interface name too long")
    return iface


class TSharkSensor:
    """Manages a TShark subprocess for live packet capture.

    Produces JSON lines (one per packet) via a callback or internal queue.
    """

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
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
        return self._running and self._process is not None and self._process.poll() is None

    @property
    def stats(self) -> dict:
        with self._lock:
            return dict(self._stats)

    def start(self, interface: str, callback: Optional[Callable[[dict], None]] = None,
              bpf_filter: Optional[str] = None,
              output_format: Optional[str] = None) -> bool:
        """Start TShark capture on the given interface.

        callback: called with parsed JSON dict for each packet line.
        Returns True if started successfully.
        """
        if self.is_running:
            logger.warning("TShark already running — stopping first")
            self.stop()

        iface = _validate_interface(interface)
        fmt = output_format or TSHARK_OUTPUT_FORMAT
        snaplen = str(TSHARK_SNAPLEN)

        cmd = [
            TSHARK_PATH,
            "-i", iface,
            "-l",
            "-T", fmt,
            "-a", "duration:3600",
        ]
        if snaplen and snaplen != "0":
            cmd.extend(["-s", snaplen])
        if TSHARK_PROMISCUOUS:
            cmd.insert(3, "-p")
        bf = bpf_filter or TSHARK_BPF_FILTER
        if bf:
            cmd.extend(["-f", bf])

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
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                bufsize=1,
                text=True,
            )
        except FileNotFoundError:
            with self._lock:
                self._stats["error"] = "TShark executable not found"
            logger.error("TShark executable not found at: %s", TSHARK_PATH)
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
            if self._process and self._process.poll() is None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        self._process.kill()
                        self._process.wait(timeout=3)
                    except Exception:
                        pass
                except Exception:
                    pass
            if self._process:
                stats["exit_code"] = self._process.returncode
                self._stats["exit_code"] = self._process.returncode
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
        if not self._process or not self._process.stdout:
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
                    except Exception as e:
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
        except Exception as e:
            logger.error("TShark reader error: %s", e)
            with self._lock:
                self._stats["error"] = str(e)
        finally:
            self._running = False
            if self._process:
                stderr_data = ""
                try:
                    stderr_data = self._process.stderr.read(4096) if self._process.stderr else ""
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
        if self._process and self._process.poll() is not None:
            code = self._process.returncode
            with self._lock:
                err = self._stats.get("error", "")
            return f"TShark exited with code {code}: {err}"
        return None
