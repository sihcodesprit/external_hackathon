"""TShark discovery, validation and probing — the single source of truth.

Every module in the project that needs TShark must go through this locator.
There is intentionally NO duplicated discovery logic anywhere else.

Resolution priority:
    1. ``TSHARK_PATH`` environment variable (explicit user override)
    2. ``NETWATCH_TSHARK_PATH`` environment variable (legacy alias)
    3. ``tshark`` available directly on ``PATH``
    4. Automatic executable discovery (platform candidate paths)
    5. Clear error (setup scripts then install TShark / print install hints)

The candidate paths below are *documented discovery candidates* only — they
are checked and verified against the filesystem, never assumed to exist.
"""

from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_TSHARK_BIN = "tshark.exe" if platform.system().lower() == "windows" else "tshark"

# Probing spawns `tshark --version` and walks PATH / the filesystem; the
# dashboard polls this frequently, so cache the result briefly.
_PROBE_TTL_SECONDS = float(os.environ.get("NETWATCH_TSHARK_PROBE_TTL", "120"))
_probe_cache: dict = {}

# Npcap / WinPcap capture driver DLLs (Windows only). These are only existence
# probes — Wireshark/Npcap ships the WinPcap DLL even when libpcap is used.
_NPCAP_DLLS = (
    r"C:\Windows\System32\Npcap\wpcap.dll",
    r"C:\Windows\SysWOW64\Npcap\wpcap.dll",
    r"C:\Program Files\Npcap\wpcap.dll",
)

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


# ── Environment hints ────────────────────────────────────────────────
def env_tshark_hint() -> Optional[str]:
    """Return the explicitly configured TShark path (if any) from env vars."""
    for key in ("TSHARK_PATH", "NETWATCH_TSHARK_PATH"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


# ── Candidate discovery paths (documented candidates, verified on disk) ─
def _windows_candidates() -> List[str]:
    candidates: List[str] = []
    base_dirs = (
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", os.path.expandvars(r"%LOCALAPPDATA%")),
    )
    for base in base_dirs:
        if not base:
            continue
        if base == os.environ.get("LOCALAPPDATA", ""):
            candidates.append(str(Path(base) / "Programs" / "Wireshark" / _TSHARK_BIN))
            candidates.append(str(Path(base) / "Wireshark" / _TSHARK_BIN))
        else:
            candidates.append(str(Path(base) / "Wireshark" / _TSHARK_BIN))
    # Scoop / per-user installs
    candidates.append(str(Path.home() / "scoop" / "apps" / "wireshark" / "current" / _TSHARK_BIN))
    # InstallDir keys written by the Wireshark installer
    try:
        if sys.platform.startswith("win"):
            import winreg

            for hive, subkey in (
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wireshark"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Wireshark"),
            ):
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                    if install_dir:
                        candidates.append(str(Path(install_dir) / _TSHARK_BIN))
                except OSError:
                    pass
    except Exception:  # noqa: BLE001  (registry probing must never crash discovery)
        pass
    # De-duplicate while preserving order
    seen: set = set()
    unique = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _posix_candidates() -> List[str]:
    return [
        "/usr/bin/tshark",
        "/usr/local/bin/tshark",
        "/opt/wireshark/bin/tshark",
        "/opt/homebrew/bin/tshark",
        "/snap/bin/tshark",
        "/Applications/Wireshark.app/Contents/MacOS/tshark",
    ]


def discover_candidates() -> List[str]:
    """Ordered list of plausible TShark install locations (never assumed)."""
    if platform.system().lower() == "windows":
        return _windows_candidates()
    return _posix_candidates()


# ── Version probing ──────────────────────────────────────────────────
def _probe_version(exe: str) -> Optional[str]:
    """Run ``tshark --version`` and return a short ``X.Y.Z`` version string."""
    try:
        result = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            shell=False,
        )
        output = (result.stdout or result.stderr or "").strip()
    except Exception as e:  # noqa: BLE001
        logger.debug("Could not run tshark --version (%s): %s", exe, e)
        return None

    first_line = output.splitlines()[0].strip() if output else ""
    match = _VERSION_RE.search(first_line)
    if match:
        return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
    return first_line or None


def _npcap_installed() -> bool:
    """True when the Npcap (or WinPcap) capture driver DLL is present."""
    return any(os.path.exists(dll) for dll in _NPCAP_DLLS)


def _validate_path(path: str) -> bool:
    """True when ``path`` is an existing file (or resolvable binary name)."""
    if not path:
        return False
    if os.path.isabs(path):
        return os.path.isfile(path)
    return shutil.which(path) is not None


# ── Resolution ───────────────────────────────────────────────────────
def resolve_tshark(path_hint: str = "") -> Optional[str]:
    """Resolve the absolute path to a working TShark executable.

    ``path_hint`` may be a full path or a bare command name. When empty or
    ``"tshark"`` the standard priority list (env -> PATH -> candidate paths)
    is used. When a specific hint is given and it fails to resolve, ``None``
    is returned (no fallback).
    """
    hint = (path_hint or "").strip()
    env_hint = env_tshark_hint()

    # Specific hint provided (not empty, not generic "tshark")
    if hint and hint != "tshark":
        resolved = _resolve_hint(hint)
        return resolved  # No fallback - explicit hint failed

    # No specific hint → use env, PATH, candidates (auto-discovery)
    if env_hint:
        resolved = _resolve_hint(env_hint)
        if resolved:
            return resolved

    # Direct command resolution through PATH
    found = shutil.which(_TSHARK_BIN) or shutil.which("tshark")
    if found:
        return found

    # Filesystem candidate walk (verified against the filesystem)
    for candidate in discover_candidates():
        if os.path.isfile(candidate):
            return candidate
    return None


def _resolve_hint(hint: str) -> Optional[str]:
    if os.path.isabs(hint):
        if os.path.isfile(hint):
            return os.path.abspath(hint)
        return None
    resolved = shutil.which(hint)
    return resolved


# ── Public probing API ───────────────────────────────────────────────
def _is_fresh(entry) -> bool:
    return entry is not None and (time.monotonic() - entry[0]) < _PROBE_TTL_SECONDS


def locate_tshark(path_hint: str = "") -> Optional[str]:
    """Absolute TShark path, or None when not installed. Cached briefly."""
    key = path_hint or "auto"
    cached = _probe_cache.get(key)
    if _is_fresh(cached):
        return cached[1]
    path = resolve_tshark(path_hint)
    _probe_cache[key] = (time.monotonic(), path)
    return path


def validate_tshark(path_hint: str = "") -> dict:
    """Validate the TShark executable: existence + executable version probe."""
    resolved = locate_tshark(path_hint)
    if not resolved:
        return {"valid": False, "path": None, "version": None, "error": "Not found"}

    version = _probe_version(resolved)
    return {
        "valid": version is not None,
        "path": resolved,
        "version": version,
        "error": None if version is not None else "Executable found but version probe failed",
    }


def get_tshark_version(path_hint: str = "") -> Optional[str]:
    info = validate_tshark(path_hint)
    return info.get("version")


def is_tshark_available(path_hint: str = "") -> bool:
    return locate_tshark(path_hint) is not None


def _capture_available(resolved: str) -> bool:
    """Heuristic capture availability (full permission is verified at start).

    Windows: the Npcap/WinPcap driver DLL must be present.
    POSIX:   presence is reported; root / CAP_NET_RAW is verified by probes.
    """
    if platform.system().lower() == "windows":
        return _npcap_installed()
    return True


def _info_cache_key(path_hint: str) -> str:
    return f"info::{path_hint or 'auto'}"


def find_tshark(path_hint: str = "") -> dict:
    """Full TShark health info (legacy-compatible shape), cached briefly."""
    key = _info_cache_key(path_hint)
    cached = _probe_cache.get(key)
    if _is_fresh(cached):
        return dict(cached[1])

    resolved = locate_tshark(path_hint)
    if not resolved:
        info = {
            "installed": False,
            "path": None,
            "version": None,
            "platform": platform.system().lower(),
            "capture_available": False,
            "reason": "TShark executable not found",
        }
        _probe_cache[key] = (time.monotonic(), info)
        return dict(info)

    version = _probe_version(resolved)
    info = {
        "installed": True,
        "path": resolved,
        "version": version,
        "platform": platform.system().lower(),
        "capture_available": _capture_available(resolved),
        "reason": None,
    }
    _probe_cache[key] = (time.monotonic(), info)
    return dict(info)


def health_check(path_hint: str = "") -> dict:
    """Nested health-check shape."""
    info = find_tshark(path_hint)
    return {
        "tshark": {
            "installed": info["installed"],
            "path": info["path"],
            "version": info["version"],
        },
        "platform": info.get("platform"),
        "capture_available": info["capture_available"],
    }


def detect_tshark(path_hint: str = "") -> dict:
    """Flat probe shape consumed by the dashboard /api/live/health endpoint."""
    info = find_tshark(path_hint)
    return {
        "available": bool(info["installed"] and info["capture_available"]),
        "installed": info["installed"],
        "capture_available": info["capture_available"],
        "path": info["path"],
        "version": info["version"],
        "platform": info["platform"],
        "reason": info.get("reason"),
        "error": None if info["installed"] else
            "tshark not found. Run scripts/check_tshark.py or scripts/setup.py "
            "to install and configure TShark.",
    }


def get_tshark_capabilities(path_hint: str = "") -> dict:
    """Rich capability report used by /api/system/dependencies and self-tests."""
    info = find_tshark(path_hint)
    return {
        "available": bool(info["installed"] and info["capture_available"]),
        "path": info["path"],
        "version": info["version"],
        "platform": info["platform"],
        "capture_available": info["capture_available"],
        "reason": info.get("reason"),
        "interfaces_available": False,
        "error": info.get("reason"),
    }
