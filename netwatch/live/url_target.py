"""URL target resolution and filtering for the live URL monitor.

A URL is used ONLY to identify the remote destination infrastructure that
can be observed from the local capture point:

    URL -> scheme/hostname/port -> DNS resolution -> resolved IP set -> filter

This module NEVER issues HTTP requests to the supplied URL (no SSRF). The
only outbound network activity is DNS name resolution performed by the OS.
"""

import ipaddress
import logging
import re
import socket
import urllib.parse
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

# Only http/https are monitored. Everything else is rejected (file:, data:,
# javascript:, shell command strings, ...).
ALLOWED_SCHEMES = ("http", "https")
_DEFAULT_PORTS = {"http": 80, "https": 443}

_LOOPBACK_HOSTS = ("localhost", "localhost.localdomain")

# Hostnames may contain letters/digits/hyphens/dots and optional trailing dot.
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9\-.]*[A-Za-z0-9])?\.?$")


def _is_ip_string(s: str) -> bool:
    try:
        ipaddress.ip_address(s.split("%")[0])
        return True
    except ValueError:
        return False


def is_loopback_or_private(host: str) -> bool:
    """True when a hostname/IP points at loopback, private/internal space.

    These are rejected by default (SSRF hardening) unless the operator
    explicitly enables a controlled-lab bypass via config.
    """
    host = (host or "").strip().lower().rstrip(".")
    if not host:
        return True
    if _is_ip_string(host):
        try:
            ip = ipaddress.ip_address(host.split("%")[0])
        except ValueError:
            return True
        return bool(ip.is_loopback or ip.is_unspecified or ip.is_reserved
                    or ip.is_link_local or ip.is_multicast
                    or ip.is_private or ip.is_shared)
    if host in _LOOPBACK_HOSTS or host.endswith(".localhost"):
        return True
    # RFC 6762 / RFC 6761 special-use names — not routable destinations.
    if host.endswith(".local") or host.endswith(".intranet"):
        return True
    return False


def validate_hostname(host: str) -> str:
    """Validate a hostname / IP literal. Returns canonical lowercased form."""
    host = (host or "").strip()
    if not host:
        raise ValueError("Hostname is required")
    if len(host) > 253:
        raise ValueError("Hostname too long")
    if host.endswith("."):
        host = host[:-1]
    if _is_ip_string(host):
        return host
    if not _HOSTNAME_RE.match(host):
        raise ValueError(f"Invalid hostname: {host!r}")
    lower = host.lower()
    return lower


class UrlParseResult:
    """Validated, parsed URL target identity."""

    def __init__(self, url: str, allow_private_hosts: bool = False):
        self.url = url
        self.scheme = ""
        self.hostname = ""
        self.port = 0
        self.path = ""
        self._allow_private_hosts = allow_private_hosts
        self._parse()

    def _parse(self):
        parsed = urllib.parse.urlsplit(self.url)
        scheme = (parsed.scheme or "").strip().lower()
        if scheme not in ALLOWED_SCHEMES:
            raise ValueError(
                f"Unsupported URL scheme {scheme!r}. Only http and https are supported.")
        host = parsed.hostname
        if host is None or not host.strip():
            raise ValueError("URL must include a hostname (e.g. https://example.com)")

        hostname = validate_hostname(host)
        if not self._allow_private_hosts and is_loopback_or_private(hostname):
            raise ValueError(
                f"Host {hostname!r} is a loopback/private address. "
                "Public destinations only unless NETWATCH_LIVE_URL_ALLOW_PRIVATE_HOSTS=1.")

        self.scheme = scheme
        self.hostname = hostname

        if parsed.port is not None:
            try:
                port = int(parsed.port)
            except (TypeError, ValueError):
                port = -1
            if not (1 <= port <= 65535):
                raise ValueError(f"Invalid port in URL: {parsed.port!r}")
            self.port = port
        else:
            self.port = _DEFAULT_PORTS[scheme]

        self.path = parsed.path or "/"
        # The path is display metadata only — it is NEVER used as a capture filter.

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "scheme": self.scheme.upper(),
            "hostname": self.hostname,
            "port": self.port,
            "path": self.path,
        }


def resolve_hostname(hostname: str) -> List[str]:
    """Resolve a hostname to its full set of currently-known IP addresses.

    Returns IPv4 and IPv6 literals (deduplicated), covering multiple A/AAAA
    records and CDN edge servers. Empty list when nothing resolves.
    """
    seen: Set[str] = set()
    out: List[str] = []
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            infos = socket.getaddrinfo(hostname, None, family, socket.SOCK_STREAM)
        except socket.gaierror:
            infos = []
        except OSError:
            infos = []
        for info in infos:
            ip = str(info[4][0])
            if "%" in ip:  # strip IPv6 zone id (fe80::1%eth0)
                ip = ip.split("%", 1)[0]
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                continue
            if addr.version == 6 and addr.ipv4_mapped is not None:
                ip = str(addr.ipv4_mapped)
                addr = ipaddress.ip_address(ip)
            if ip not in seen:
                seen.add(ip)
                out.append(ip)
    return out


def build_bpf_filter(ips: List[str], port: Optional[int]) -> str:
    """Build a tshark capture (BPF) filter for a resolved IP set + port.

    Returns "" when there is nothing to filter (capture everything and let
    the Python matcher filter). Never constructed from raw user input.
    """
    ips = [ip for ip in ips if ip]
    if not ips:
        return ""
    host_expr = " or ".join(f"host {ip}" for ip in ips)
    expr = f"({host_expr})" if len(ips) > 1 else host_expr
    if port:
        expr = f"{expr} and port {port}"
    return expr


class UrlTarget:
    """A live URL target with a continuously-maintained destination IP set."""

    def __init__(self, url: str, allow_private_hosts: bool = False):
        self._allow_private_hosts = allow_private_hosts
        self._parse = UrlParseResult(url, allow_private_hosts=allow_private_hosts)
        self.current_ips: List[str] = []
        self.previous_ips: List[str] = []
        self.ip_history: List[dict] = []
        self.resolution_count = 0
        self.last_resolved_at: Optional[float] = None

    @property
    def url(self) -> str:
        return self._parse.url

    @property
    def hostname(self) -> str:
        return self._parse.hostname

    @property
    def scheme(self) -> str:
        return self._parse.scheme

    @property
    def port(self) -> int:
        return self._parse.port

    @property
    def path(self) -> str:
        return self._parse.path

    @property
    def protocol(self) -> str:
        return "HTTPS" if self.scheme == "https" else "HTTP"

    def resolve(self) -> List[str]:
        """Re-resolve the hostname and merge results into the target state.

        Returns the new IP list. IP set changes are recorded for the dashboard.
        """
        ips = resolve_hostname(self.hostname)
        self.previous_ips = list(self.current_ips)
        self.current_ips = ips
        self.resolution_count += 1
        self.ip_history.append({
            "resolved_at": self.last_resolved_at,
            "ips": list(ips),
        })
        self.ip_history = self.ip_history[-50:]
        return ips

    def matches(self, event: dict) -> bool:
        """True when an observed packet involves a current target endpoint.

        Matching is IP-based (the primary network identity). For TCP/UDP the
        target port is also required so unrelated P2P/CDN chatter on other
        ports is not attributed to the URL.
        """
        if not self.current_ips:
            return False
        ips = set(self.current_ips)
        src = str(event.get("src_ip") or "")
        dst = str(event.get("dst_ip") or "")
        if not src or not dst:
            return False
        target_endpoint = src in ips or dst in ips
        if not target_endpoint:
            return False
        protocol = str(event.get("protocol") or "").upper()
        if protocol in ("TCP", "UDP") and self.port:
            sp = int(event.get("src_port") or 0)
            dp = int(event.get("dst_port") or 0)
            if sp != self.port and dp != self.port:
                return False
        return True

    def classify_direction(self, event: dict) -> str:
        """'outbound' = Linux host -> target, 'inbound' = target -> Linux host."""
        ips = set(self.current_ips)
        dst = str(event.get("dst_ip") or "")
        if dst in ips:
            return "outbound"
        return "inbound"

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "hostname": self.hostname,
            "scheme": self.scheme.upper(),
            "port": self.port,
            "path": self.path,
            "protocol": self.protocol,
            "resolved_ips": list(self.current_ips),
            "previous_ips": list(self.previous_ips),
            "ip_history": list(self.ip_history),
            "resolution_count": self.resolution_count,
        }


def parse_url_target(url: str) -> UrlTarget:
    """Validate a URL and return a UrlTarget (no DNS performed)."""
    return UrlTarget(url)
