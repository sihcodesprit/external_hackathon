#!/usr/bin/env python3
"""TShark environment check and self-test.

Outputs a formatted status report matching the master prompt specification.
"""

import platform
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from netwatch.live.config import (
    LIVE_ENABLED,
    LIVE_FORECAST_HORIZON,
    LIVE_STEP_SIZE,
    LIVE_WINDOW_SIZE,
    TSHARK_PATH,
)
from netwatch.live.interface import discover_interfaces
from netwatch.live.tshark_locator import detect_tshark, get_tshark_capabilities


def main() -> int:
    print("=" * 40)
    print("CYBER WORLD MODEL ENVIRONMENT CHECK")
    print("=" * 40)
    print()

    # Operating System
    print("Operating System:")
    print(f"  {platform.system()} {platform.release()} ({platform.machine()})")
    print()

    # Python
    print("Python:")
    print(f"  {sys.version.split()[0]} ({platform.python_implementation()})")
    print()

    # TShark
    print("TShark:")
    info = detect_tshark(TSHARK_PATH)
    if info.get("available"):
        print("  AVAILABLE")
    elif info.get("installed"):
        print("  INSTALLED (capture unavailable)")
    else:
        print("  NOT AVAILABLE")

    if info.get("path"):
        print("TShark Path:")
        print(f"  {info['path']}")

    if info.get("version"):
        print("TShark Version:")
        print(f"  {info['version']}")

    print("Platform:")
    print(f"  {info.get('platform', 'unknown')}")

    if info.get("reason"):
        print("Reason:")
        print(f"  {info['reason']}")

    if info.get("error"):
        print("Error:")
        print(f"  {info['error']}")

    print()

    # Live capture capability
    caps = get_tshark_capabilities(TSHARK_PATH)
    if caps.get("available"):
        print("Live Capture:")
        print("  READY")
    else:
        print("Live Capture:")
        print("  NOT READY")
        if caps.get("reason"):
            print(f"  Reason: {caps['reason']}")

    print()

    # PATH / configuration
    print("PATH Configuration:")
    if TSHARK_PATH:
        print(f"  TSHARK_PATH set explicitly: {TSHARK_PATH}")
    else:
        print("  Auto-discovery mode (TSHARK_PATH not set)")
    print()

    # Available interfaces
    print("Available Interfaces:")
    ifaces = discover_interfaces()
    up_ifaces = [i for i in ifaces if str(i.get("state", "")).upper() == "UP" and not i.get("is_loopback", False)]
    if up_ifaces:
        for i in up_ifaces[:5]:
            addrs = i.get("addresses", [])
            addr_str = addrs[0].get("addr") if addrs else "no IP"
            print(f"  * {i['name']} ({addr_str})")
    else:
        print("  (none suitable for capture)")
    print()

    # Live config summary
    print("Live Pipeline Config:")
    print(f"  Enabled: {LIVE_ENABLED}")
    print(f"  Window: {LIVE_WINDOW_SIZE}s, Step: {LIVE_STEP_SIZE}s, Horizon: {LIVE_FORECAST_HORIZON} steps")
    print()

    if info.get("available"):
        print("=" * 40)
        print("SETUP COMPLETE")
        print("=" * 40)
        return 0
    else:
        print("=" * 40)
        print("SETUP INCOMPLETE - TShark not ready")
        print("=" * 40)
        return 1


if __name__ == "__main__":
    sys.exit(main())
