#!/usr/bin/env python3
"""One-command setup for NetWatch — installs Python deps, discovers/installs TShark.

Usage:
    python scripts/setup.py

Platform detection and appropriate install flow:
    - Windows: tries winget -> choco -> manual instructions
    - Linux: apt (Debian/Ubuntu/Kali) -> dnf (Fedora/RHEL) -> pacman (Arch)
    - macOS: Homebrew
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from scripts._setup_common import (
    REPO_ROOT,
    LOG,
    detect_python,
    discover_tshark_path,
    ensure_venv,
    load_dotenv,
    pip_install,
    print_banner,
    print_step,
    run_cmd,
    verify_tshark,
    write_env,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)

TOTAL_STEPS = 7


def setup_python() -> Path:
    """Ensure Python >=3.10 and create venv."""
    print_step(1, TOTAL_STEPS, "Checking Python", "PASS")
    py = detect_python()
    print(f"         Found: {py} ({platform.python_version()})")
    return ensure_venv()


def install_python_deps(python: Path) -> None:
    """Install requirements.txt into venv."""
    print_step(2, TOTAL_STEPS, "Installing Python dependencies", "PASS")
    req = REPO_ROOT / "requirements.txt"
    if req.exists():
        pip_install(python, ["-r", str(req)])
    else:
        LOG.warning("requirements.txt not found — skipping")


def check_tshark() -> Optional[Path]:
    """Discover TShark executable."""
    print_step(3, TOTAL_STEPS, "Checking TShark", "PASS")
    tshark = discover_tshark_path()
    if tshark:
        ok, ver, err = verify_tshark(tshark)
        if ok:
            print(f"         Found: {tshark} ({ver})")
            return tshark
        print(f"         Found but verification failed: {err}")
    print("         Not found")
    return None


def install_tshark_windows() -> Optional[Path]:
    """Install TShark on Windows via winget/choco."""
    LOG.info("Attempting Windows TShark installation...")
    # winget preferred
    if shutil.which("winget"):
        try:
            print("         winget found — installing Wireshark (includes TShark)...")
            print("         ⚠ Windows may show a UAC prompt for installation.")
            run_cmd([
                "winget", "install", "--id", "WiresharkFoundation.Wireshark",
                "-e", "--silent", "--accept-package-agreements",
                "--accept-source-agreements", "--disable-interactivity"
            ], capture=True, check=True)
            print("         winget install completed")
            return discover_tshark_path()
        except subprocess.CalledProcessError as e:
            LOG.warning("winget install failed: %s", e)
    # Chocolatey fallback
    if shutil.which("choco"):
        try:
            print("         Chocolatey found — installing wireshark...")
            run_cmd(["choco", "install", "wireshark", "-y"], capture=True, check=True)
            print("         Chocolatey install completed")
            return discover_tshark_path()
        except subprocess.CalledProcessError as e:
            LOG.warning("choco install failed: %s", e)
    print("         No supported package manager found (winget/choco).")
    print("         Please install Wireshark manually from https://www.wireshark.org/download.html")
    return None


def install_tshark_linux() -> Optional[Path]:
    """Install TShark on Linux via package manager."""
    if shutil.which("apt-get") or shutil.which("apt"):
        try:
            print("         apt found — installing tshark...")
            run_cmd(["apt-get", "update"], capture=True, check=False)
            run_cmd(["apt-get", "install", "-y", "tshark"], capture=True, check=True)
            return discover_tshark_path()
        except subprocess.CalledProcessError as e:
            LOG.warning("apt install failed: %s", e)
    if shutil.which("dnf"):
        try:
            print("         dnf found — installing wireshark-cli...")
            run_cmd(["dnf", "install", "-y", "wireshark-cli"], capture=True, check=True)
            return discover_tshark_path()
        except subprocess.CalledProcessError as e:
            LOG.warning("dnf install failed: %s", e)
    if shutil.which("pacman"):
        try:
            print("         pacman found — installing wireshark-cli...")
            run_cmd(["pacman", "-Sy", "--noconfirm", "wireshark-cli"], capture=True, check=True)
            return discover_tshark_path()
        except subprocess.CalledProcessError as e:
            LOG.warning("pacman install failed: %s", e)
    if shutil.which("zypper"):
        try:
            print("         zypper found — installing wireshark...")
            run_cmd(["zypper", "install", "-y", "wireshark"], capture=True, check=True)
            return discover_tshark_path()
        except subprocess.CalledProcessError as e:
            LOG.warning("zypper install failed: %s", e)
    print("         No supported package manager found.")
    print("         Please install tshark/wireshark-cli via your distribution's package manager.")
    return None


def install_tshark_macos() -> Optional[Path]:
    """Install TShark on macOS via Homebrew."""
    if shutil.which("brew"):
        try:
            print("         Homebrew found — installing wireshark...")
            run_cmd(["brew", "install", "wireshark"], capture=True, check=True)
            return discover_tshark_path()
        except subprocess.CalledProcessError as e:
            LOG.warning("brew install failed: %s", e)
    print("         Homebrew not found. Please install from https://brew.sh or")
    print("         download Wireshark from https://www.wireshark.org/download.html")
    return None


def install_tshark() -> Optional[Path]:
    """Platform-specific TShark installation."""
    print_step(4, TOTAL_STEPS, "Installing TShark", "PASS")
    system = platform.system().lower()
    if system == "windows":
        return install_tshark_windows()
    elif system == "linux":
        return install_tshark_linux()
    elif system == "darwin":
        return install_tshark_macos()
    else:
        print(f"         Unsupported platform: {system}")
        return None


def configure_tshark(tshark_path: Optional[Path]) -> bool:
    """Configure TSHARK_PATH in .env and optionally add to user PATH."""
    print_step(5, TOTAL_STEPS, "Configuring TShark", "PASS")
    if not tshark_path:
        print("         No TShark path to configure")
        return False

    # Write TSHARK_PATH to .env
    write_env("TSHARK_PATH", str(tshark_path))
    print(f"         Set TSHARK_PATH={tshark_path} in .env")

    # On Windows, also offer to add Wireshark directory to USER PATH
    if sys.platform == "win32":
        tshark_dir = tshark_path.parent
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                try:
                    user_path, _ = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    user_path = ""
                if str(tshark_dir).lower() not in user_path.lower():
                    new_path = user_path + (";" if user_path else "") + str(tshark_dir)
                    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
                    print(f"         Added {tshark_dir} to USER PATH (requires shell restart)")
                    # Broadcast environment change
                    import ctypes
                    ctypes.windll.user32.SendMessageTimeoutW(
                        0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None
                    )
                else:
                    print("         Wireshark directory already in USER PATH")
        except Exception as e:  # noqa: BLE001
            LOG.debug("Could not update USER PATH: %s", e)

    return True


def verify_setup(tshark_path: Optional[Path]) -> bool:
    """Run final verification."""
    print_step(6, TOTAL_STEPS, "Verifying setup", "PASS")

    # Python check
    py = detect_python()
    print(f"         Python: {py} ({platform.python_version()})")

    # TShark check
    if tshark_path:
        ok, ver, err = verify_tshark(tshark_path)
        if ok:
            print(f"         TShark: {tshark_path} ({ver})")
        else:
            print(f"         TShark: FAILED - {err}")
            return False
    else:
        print("         TShark: NOT AVAILABLE (live monitoring disabled)")

    # Import check
    try:
        from netwatch.live.tshark_locator import detect_tshark
        from netwatch.live.config import TSHARK_PATH
        info = detect_tshark(TSHARK_PATH)
        print(f"         Locator: available={info.get('available')}, path={info.get('path')}")
    except Exception as e:
        LOG.warning("Locator import failed: %s", e)

    return True


def run_capture_self_test(tshark_path: Path) -> bool:
    """Short live capture test against first available interface."""
    print_step(7, TOTAL_STEPS, "Running capture self-test", "PASS")
    try:
        from netwatch.live.interface import discover_interfaces
        from netwatch.live.tshark_command import build_short_capture_command

        ifaces = discover_interfaces()
        up_ifaces = [i for i in ifaces if str(i.get("state", "")).upper() == "UP" and not i.get("is_loopback", False)]
        if not up_ifaces:
            print("         No suitable interfaces found for capture test")
            return True  # Not a failure — just no test interface

        iface = up_ifaces[0].get("name", "")
        if not iface:
            print("         No valid interface name")
            return True

        print(f"         Testing capture on interface: {iface}")
        cmd = build_short_capture_command(str(tshark_path), iface, duration=3, snaplen=256)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False)
        try:
            stdout, stderr = proc.communicate(timeout=10)
            if proc.returncode == 0 or (stdout and stdout.strip()):
                print("         Capture test: OK (TShark started and produced output)")
            else:
                print(f"         Capture test: TShark exited ({proc.returncode}) - {stderr[:200] if stderr else ''}")
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            if stdout and stdout.strip():
                print("         Capture test: OK (TShark running, received packets)")
            else:
                print(f"         Capture test: no packets in 3s (may be idle network) - {stderr[:200] if stderr else ''}")
    except Exception as e:  # noqa: BLE001
        LOG.warning("Self-test error: %s", e)
        print(f"         Capture test: skipped ({e})")
    return True


def main() -> int:
    print_banner("NETWATCH SETUP")
    print(f"Repository: {REPO_ROOT}")
    print(f"Platform: {platform.system()} {platform.release()}")

    load_dotenv()

    # 1. Python + venv
    python = setup_python()

    # 2. Python dependencies
    install_python_deps(python)

    # 3. Check TShark
    tshark = check_tshark()

    # 4. Install TShark if missing
    if not tshark:
        tshark = install_tshark()

    # 5. Configure
    configure_tshark(tshark)

    # 6. Verify
    ok = verify_setup(tshark)

    # 7. Self-test (optional, non-blocking)
    if tshark:
        run_capture_self_test(tshark)

    print_banner("SETUP COMPLETE" if ok else "SETUP COMPLETED WITH WARNINGS")

    if not tshark:
        print("TShark was not installed/configured.")
        print("Live network monitoring will be DISABLED.")
        print("Offline modes (PCAP/CSV/JSONL/synthetic) still work.")
        print("")
        print("To enable live monitoring:")
        print("  1. Install Wireshark/TShark manually")
        print("  2. Re-run this setup script")
        return 1

    print("")
    print("Next steps:")
    print(f"  {REPO_ROOT / 'venv' / ('Scripts' if sys.platform == 'win32' else 'bin') / 'python'} run.py")
    print("  # then open http://localhost:5000")
    print("")
    print("Live Monitor: http://localhost:5000/live")
    print("URL Monitor:  http://localhost:5000/url-monitor")
    print("System:       http://localhost:5000/system")
    return 0


if __name__ == "__main__":
    sys.exit(main())