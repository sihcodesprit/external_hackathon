"""TShark process runner abstraction.

Separates process execution from the rest of the pipeline so that unit tests
and CI can run without a real TShark install:

- ``TsharkRunner``   — interface (launch / terminate / read output)
- ``RealTsharkRunner`` — subprocess-based implementation (production)
- ``MockTsharkRunner`` — scripted output lines (tests / CI / development)
"""

from __future__ import annotations

import logging
import subprocess
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)


class TsharkRunner:
    """Interface for launching and stopping a TShark subprocess.

    ``launch`` returns an opaque process handle whose interface mirrors the
    subset of ``subprocess.Popen`` used by the sensor:

        proc.poll()          -> Optional[int]
        proc.returncode      -> int | None
        proc.terminate()     -> None
        proc.kill()          -> None
        proc.wait(timeout)   -> int
        proc.stdout          -> iterable of str lines (enabled when
                               ``text=True``) OR an iterable of raw bytes
        proc.stderr          -> file-like (readable tail)
    """

    def launch(self, cmd: List[str], **kwargs) -> object:  # pragma: no cover - interface
        raise NotImplementedError

    def terminate(self, proc, grace: float = 5.0, hard: float = 3.0) -> Optional[int]:
        """Stop a process: SIGTERM first, fall back to SIGKILL. Returns exit code."""
        if proc is None:
            return None
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=grace)
        except Exception:  # noqa: BLE001
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=hard)
            except Exception:  # noqa: BLE001
                pass
        return proc.returncode


class RealTsharkRunner(TsharkRunner):
    """Production runner backed by ``subprocess.Popen`` (always shell=False)."""

    def launch(self, cmd: List[str], **kwargs) -> "subprocess.Popen":
        options = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "shell": False,
            "bufsize": 1,
            "text": True,
        }
        options.update(kwargs)
        return subprocess.Popen(cmd, **options)


class MockTsharkRunner(TsharkRunner):
    """Scripted runner that never touches a real TShark process.

    ``output_lines`` is an iterable of strings delivered as the process
    ``stdout``; ``stderr_tail`` is returned on stop. Useful in unit tests.
    """

    def __init__(self, output_lines: Optional[Iterable[str]] = None,
                 stderr_tail: str = "", exit_code: Optional[int] = 0,
                 fail_on_launch: bool = False):
        self.output_lines = list(output_lines or [])
        self.stderr_tail = stderr_tail
        self.exit_code = exit_code
        self.fail_on_launch = fail_on_launch
        self.launched_commands: List[List[str]] = []

    def launch(self, cmd: List[str], **kwargs) -> object:
        self.launched_commands.append(list(cmd))
        if self.fail_on_launch:
            raise FileNotFoundError(f"{cmd[0]} not found")
        return _MockProc(self.output_lines, self.stderr_tail, self.exit_code)


class _MockProc:
    """Minimal stand-in for ``subprocess.Popen`` exposed by MockTsharkRunner."""

    def __init__(self, output_lines: Iterable[str], stderr_tail: str, exit_code: Optional[int]):
        self.stdout = iter(output_lines)
        self.stderr = _MockStderr(stderr_tail)
        self.returncode = exit_code
        self._terminated = False

    def poll(self) -> Optional[int]:
        if self._terminated:
            return self.returncode
        return None

    def terminate(self) -> None:
        self._terminated = True

    def kill(self) -> None:
        self._terminated = True

    def wait(self, timeout: Optional[float] = None) -> Optional[int]:
        self._terminated = True
        return self.returncode


class _MockStderr:
    def __init__(self, tail: str):
        self._tail = tail
        self._read = False

    def read(self, _n: int = 0) -> str:
        if self._read:
            return ""
        self._read = True
        return self._tail