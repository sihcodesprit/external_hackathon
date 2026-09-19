#!/usr/bin/env python3
"""Shared utilities for setup scripts."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG = logging.getLogger("netwatch.setup")


def run_cmd(cmd: List[str], capture: bool = True, check: bool = True, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a command and return CompletedProcess."""
    LOG.debug("Running: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check,
        cwd=str(cwd or REPO_ROOT),
        shell=False,
    )


def which(cmd: str) -> Optional[str]:
    """Return absolute path if command exists on PATH."""
    return shutil.which(cmd)


def load_dotenv(path: Optional[Path] = None) -> None:
    """Load KEY=VALUE from .env into os.environ (no override)."""
    path = path or REPO_ROOT / ".env"
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception as e:  # noqa: BLE001
        LOG.debug("Failed to load .env: %s", e)


def write_env(key: str, value: str, path: Optional[Path] = None) -> None:
    """Write or update KEY=VALUE in .env file."""
    path = path or REPO_ROOT / ".env"
    lines = []
    found = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_venv() -> Path:
    """Create venv if missing, return venv python path."""
    venv_dir = REPO_ROOT / "venv"
    python_exe = venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
    if not python_exe.exists():
        LOG.info("Creating virtual environment at %s", venv_dir)
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        LOG.info("Virtual environment created")
    return python_exe


def pip_install(python: Path, packages: List[str]) -> None:
    """Install packages with pip using the given python."""
    cmd = [str(python), "-m", "pip", "install", "-q", "--upgrade", "pip"]
    subprocess.run(cmd, check=True, capture_output=True)
    if packages:
        cmd = [str(python), "-m", "pip", "install", "-q"] + packages
        subprocess.run(cmd, check=True, capture_output=True)


def print_banner(msg: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}\n")


def print_step(step: int, total: int, msg: str, status: str = "PASS") -> None:
    mark = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⚠"
    color = "\033[92m" if status == "PASS" else "\033[91m" if status == "FAIL" else "\033[93m"
    reset = "\033[0m"
    print(f"  [{color}[{step}/{total}]{reset}] {msg} ... {color}{mark} {status}{reset}")


def detect_python() -> Path:
    """Return path to a suitable Python interpreter (>=3.10)."""
    for name in ("python3", "python"):
        p = which(name)
        if p:
            try:
                out = subprocess.run([p, "-c", "import sys; print(sys.version_info[:2])"],
                                     capture_output=True, text=True, check=True)
                major, minor = eval(out.stdout.strip())
                if major >= 3 and minor >= 10:
                    return Path(p)
            except Exception:
                pass
    return Path(sys.executable)


def discover_tshark_path() -> Optional[Path]:
    """Return TShark path if available on PATH or in known locations."""
    from netwatch.live.tshark_locator import locate_tshark
    path = locate_tshark("")
    return Path(path) if path else None


def verify_tshark(tshark_path: Path) -> Tuple[bool, Optional[str], Optional[str]]:
    """Run tshark --version and return (ok, version, error)."""
    try:
        res = run_cmd([str(tshark_path), "--version"], capture=True, check=False)
        if res.returncode == 0:
            first = (res.stdout or "").splitlines()[0].strip()
            return True, first, None
        return False, None, (res.stderr or "").strip() or f"exit code {res.returncode}"
    except FileNotFoundError:
        return False, None, "Executable not found"
    except Exception as e:  # noqa: BLE001
        return False, None, str(e)