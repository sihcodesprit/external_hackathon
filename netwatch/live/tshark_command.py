"""Safe construction of TShark subprocess arguments.

Every TShark command in the project is built here so that:

- inputs are validated before they reach the executable,
- user-provided interface names, filters and hosts can never become shell
  syntax (we always call subprocess with a list — never a shell string),
- the list form is identical everywhere (sensor, self-tests, setup probes).
"""

from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Interface name validation is an allowlist of printable characters.
# Linux names are word chars (`-`, `_`, `.`), but Windows adapter names are
# free-form and commonly include spaces and parentheses, e.g.
# `vEthernet (WSL (Hyper-V firewall))`, or NPF device paths like
# `\Device\NPF_{GUID}`. Control characters and shell metacharacters are
# rejected so a name can never become shell syntax (defense-in-depth; the
# subprocess always runs with `shell=False`).
_VALID_IFACE_CHARS = (
    set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
    | set(" (){}[]\\*+=~#@^,")
)


def _validate_interface(iface: str) -> str:
    """Validate and return an interface name; raise ValueError when unsafe."""
    if not iface or not isinstance(iface, str):
        raise ValueError("Interface name is required")
    if not all(c in _VALID_IFACE_CHARS for c in iface):
        raise ValueError(f"Invalid interface name: {iface!r}")
    if len(iface) > 255:
        raise ValueError("Interface name too long")
    return iface


def _validate_output_format(fmt: str) -> str:
    fmt = (fmt or "ek").strip().lower()
    if fmt not in ("ek", "json", "fields"):
        raise ValueError(f"Unsupported TShark output format: {fmt!r}")
    return fmt


def _validate_bpf_filter(bpf_filter: Optional[str]) -> Optional[str]:
    """Validate a BPF filter (internally generated, never raw user input).

    Filters come from url_target.py (resolved IP sets built with ``host``
    expressions) or from project config. Because the subprocess always runs
    with ``shell=False``, the filter is only a command argument — but we still
    reject control characters and enforce a length cap.
    """
    if bpf_filter is None:
        return None
    bpf = str(bpf_filter).strip()
    if not bpf:
        return None
    if any(c in bpf for c in "\r\n\t\x00"):
        raise ValueError("BPF filter contains disallowed whitespace/control characters")
    if len(bpf) > 500:
        raise ValueError("BPF filter too long")
    return bpf


def build_version_command(executable: str) -> List[str]:
    """Arguments for ``tshark --version``."""
    return [executable, "--version"]


def build_interface_list_command(executable: str) -> List[str]:
    """Arguments for ``tshark -D`` (list capture interfaces)."""
    return [executable, "-D"]


def build_live_capture_command(
    executable: str,
    interface: str,
    output_format: str = "ek",
    bpf_filter: Optional[str] = None,
    snaplen: int = 65535,
    promiscuous: bool = True,
    duration: int = 3600,
) -> List[str]:
    """Return the argument list for a live TShark capture.

    Returns a list (never a shell string) so the subprocess can be spawned
    with ``shell=False``. ``interface`` and ``bpf_filter`` are validated.
    """
    exe = str(executable or "tshark")
    iface = _validate_interface(interface)
    fmt = _validate_output_format(output_format)
    bpf = _validate_bpf_filter(bpf_filter)

    cmd: List[str] = [exe, "-i", iface, "-l", "-T", fmt]
    if duration and duration > 0:
        cmd.extend(["-a", f"duration:{int(duration)}"])
    if promiscuous:
        cmd.append("-p")
    if snaplen and int(snaplen) > 0:
        cmd.extend(["-s", str(int(snaplen))])
    if bpf:
        cmd.extend(["-f", bpf])
    return cmd


def build_short_capture_command(
    executable: str,
    interface: str,
    output_format: str = "ek",
    bpf_filter: Optional[str] = None,
    duration: int = 3,
    snaplen: int = 256,
) -> List[str]:
    """Short controlled capture used by the self-test / setup verification."""
    return build_live_capture_command(
        executable,
        interface,
        output_format=output_format,
        bpf_filter=bpf_filter,
        snaplen=snaplen,
        promiscuous=False,
        duration=duration,
    )
