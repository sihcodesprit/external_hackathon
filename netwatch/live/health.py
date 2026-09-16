"""TShark health detection and version probing."""

import logging
import os
import platform
import shutil
import subprocess

logger = logging.getLogger(__name__)


def find_tshark(path_hint: str = "tshark") -> dict:
    """Find TShark binary and return health info."""
    resolved = shutil.which(path_hint)
    if not resolved:
        return {
            "installed": False,
            "path": None,
            "version": None,
            "platform": platform.system().lower(),
            "capture_available": False,
        }

    version = None
    try:
        r = subprocess.run(
            [resolved, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
        first = (r.stdout or "").strip().splitlines()
        if first:
            version = first[0].strip()
    except Exception as e:
        logger.debug("Could not get tshark version: %s", e)

    is_windows = platform.system().lower() == "windows"
    return {
        "installed": True,
        "path": resolved,
        "version": version,
        "platform": platform.system().lower(),
        "capture_available": not is_windows,
    }


def health_check(path_hint: str = "tshark") -> dict:
    """Full health check response."""
    info = find_tshark(path_hint)
    return {
        "tshark": {
            "installed": info["installed"],
            "path": info["path"],
            "version": info["version"],
        },
        "platform": info["platform"],
        "capture_available": info["capture_available"],
    }


def detect_tshark(path_hint: str = "tshark") -> dict:
    """Flat health probe shape consumed by the dashboard /api/live/health endpoint."""
    info = find_tshark(path_hint)
    return {
        "available": bool(info["installed"] and info["capture_available"]),
        "installed": info["installed"],
        "capture_available": info["capture_available"],
        "path": info["path"],
        "version": info["version"],
        "platform": info["platform"],
        "error": None if info["installed"] else
            "tshark not found. Install Wireshark (tshark) or set NETWATCH_TSHARK_PATH.",
    }
