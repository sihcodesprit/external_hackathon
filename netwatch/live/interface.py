"""Linux network interface discovery."""

import logging
import os
import platform
import subprocess

logger = logging.getLogger(__name__)


def discover_interfaces() -> list:
    """Detect available network interfaces on Linux.

    Tries multiple methods:
    1. psutil (if installed)
    2. /sys/class/net (Linux)
    3. `ip -j addr` (Linux iproute2)
    4. Fallback: `ifconfig -a` or `ip link`
    """
    if platform.system().lower() != "linux":
        return _discover_cross_platform()

    # Method 1: psutil
    try:
        import psutil
        return _discover_psutil()
    except ImportError:
        pass

    # Method 2: /sys/class/net
    interfaces = _discover_sysfs()
    if interfaces:
        return interfaces

    # Method 3: ip -j
    interfaces = _discover_ip_json()
    if interfaces:
        return interfaces

    return []


def _discover_cross_platform() -> list:
    """Cross-platform fallback (limited)."""
    interfaces = []
    try:
        import psutil
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        for name, stat in stats.items():
            if name == "lo":
                continue
            info = {
                "name": name,
                "state": "UP" if stat.isup else "DOWN",
                "addresses": [],
                "is_loopback": False,
                "is_virtual": _is_virtual(name),
            }
            if name in addrs:
                info["addresses"] = [
                    {"addr": a.address, "family": str(a.family)}
                    for a in addrs[name]
                    if a.address
                ]
            interfaces.append(info)
    except Exception:
        pass
    return interfaces


def _discover_psutil() -> list:
    import psutil
    interfaces = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    for name, stat in stats.items():
        info = {
            "name": name,
            "state": "UP" if stat.isup else "DOWN",
            "addresses": [],
            "is_loopback": name == "lo",
            "is_virtual": _is_virtual(name),
        }
        if name in addrs:
            info["addresses"] = [
                {"addr": a.address, "family": str(a.family)}
                for a in addrs[name]
                if a.address
            ]
        interfaces.append(info)
    return interfaces


def _discover_sysfs() -> list:
    """Read /sys/class/net/ to list interfaces."""
    net_dir = "/sys/class/net"
    if not os.path.isdir(net_dir):
        return []
    interfaces = []
    for name in sorted(os.listdir(net_dir)):
        path = os.path.join(net_dir, name)
        if not os.path.isdir(path):
            continue
        state = "DOWN"
        operstate_path = os.path.join(path, "operstate")
        if os.path.exists(operstate_path):
            try:
                with open(operstate_path) as f:
                    state = f.read().strip().upper()
            except OSError:
                pass
        interfaces.append({
            "name": name,
            "state": state,
            "addresses": _sysfs_addresses(name),
            "is_loopback": name == "lo",
            "is_virtual": _is_virtual(name),
        })
    return interfaces


def _sysfs_addresses(name: str) -> list:
    """Read addresses from /proc/net/if_inet6 or ip command."""
    addrs = []
    try:
        r = subprocess.run(
            ["ip", "-j", "addr", "show", name],
            capture_output=True, text=True, timeout=3, shell=False,
        )
        import json
        data = json.loads(r.stdout or "[]")
        if isinstance(data, list):
            for iface in data:
                for addr_info in iface.get("addr_info", []):
                    addrs.append({
                        "addr": addr_info.get("local", ""),
                        "family": addr_info.get("family", ""),
                    })
    except Exception:
        pass
    return addrs


def _discover_ip_json() -> list:
    """Parse `ip -j addr` output."""
    try:
        r = subprocess.run(
            ["ip", "-j", "addr"],
            capture_output=True, text=True, timeout=3, shell=False,
        )
        import json
        data = json.loads(r.stdout or "[]")
        interfaces = []
        for iface in data:
            name = iface.get("ifname", "")
            state = "UP" if iface.get("operstate") == "UP" else "DOWN"
            addrs = []
            for addr_info in iface.get("addr_info", []):
                addrs.append({
                    "addr": addr_info.get("local", ""),
                    "family": addr_info.get("family", ""),
                })
            interfaces.append({
                "name": name,
                "state": state,
                "addresses": addrs,
                "is_loopback": name == "lo",
                "is_virtual": _is_virtual(name),
            })
        return interfaces
    except Exception:
        return []


def _is_virtual(name: str) -> bool:
    prefixes = ("veth", "docker", "br-", "virbr", "vbox", "vmnet", "tun", "tap", "wg", "lo")
    return any(name.startswith(p) for p in prefixes)
