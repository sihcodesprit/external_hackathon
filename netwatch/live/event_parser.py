"""Parse TShark JSON/ek output lines into structured packet dicts."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# TShark EK format keys (flat path: layers.protocol.field)
_TCP_FLAGS_MAP = {
    "tcp.flags.str": None,
    "tcp.flags.syn": 0x02,
    "tcp.flags.ack": 0x10,
    "tcp.flags.reset": 0x04,
    "tcp.flags.fin": 0x01,
    "tcp.flags.push": 0x08,
    "tcp.flags.urg": 0x20,
}


def parse_ek_line(parsed: dict) -> Optional[dict]:
    """Parse a TShark EK (elasticsearch) JSON line into a flat dict.

    EK format: {"index":{"_index":"packets-...","_type":"pcap_file","_score":null}},
               {"timestamp":"...","layers":{...}}
    or inline: {"timestamp":"...","layers":{...}}

    Returns a normalized packet dict or None if unparseable.
    """
    layers = parsed.get("layers", parsed)
    if not isinstance(layers, dict):
        return None

    frame = layers.get("frame", {})
    ip_l = layers.get("ip", {})
    ipv6_l = layers.get("ipv6", layers.get("ipv6hdr", {}))
    tcp_l = layers.get("tcp", {})
    udp_l = layers.get("udp", {})
    icmp_l = layers.get("icmp", {})
    dns_l = layers.get("dns", {})
    http_l = layers.get("http", {})
    tls_l = layers.get("tls", {})

    # Timestamp
    ts_epoch = _first(frame.get("frame.time_epoch"))
    ts = _parse_epoch(ts_epoch)
    if not ts:
        return None

    # Length
    pkt_len = _to_int(_first(frame.get("frame.len")), 0)
    protocols = str(_first(frame.get("frame.protocols"), ""))

    # IP
    src_ip = str(_first(ip_l.get("ip.src", "")) or _first(ipv6_l.get("ipv6.src", "")) or "")
    dst_ip = str(_first(ip_l.get("ip.dst", "")) or _first(ipv6_l.get("ipv6.dst", "")) or "")
    if not src_ip and not dst_ip:
        return None

    proto_num = _to_int(_first(ip_l.get("ip.proto")), 0)
    ttl = _to_int(_first(ip_l.get("ip.ttl")), None) or _to_int(_first(ipv6_l.get("ipv6.hlim")), None)

    # TCP
    src_port = _to_int(_first(tcp_l.get("tcp.srcport")), 0)
    dst_port = _to_int(_first(tcp_l.get("tcp.dstport")), 0)
    tcp_flags_val = _to_int(_first(tcp_l.get("tcp.flags")), 0)
    tcp_flags_str = _build_flags_str(tcp_l, tcp_flags_val)
    tcp_window = _to_int(_first(tcp_l.get("tcp.window_size_value",
                              tcp_l.get("tcp.window_size"))), 0)

    # UDP
    if not src_port:
        src_port = _to_int(_first(udp_l.get("udp.srcport")), 0)
    if not dst_port:
        dst_port = _to_int(_first(udp_l.get("udp.dstport")), 0)

    # ICMP
    icmp_type = _to_int(_first(icmp_l.get("icmp.type")), None)
    icmp_code = _to_int(_first(icmp_l.get("icmp.code")), None)

    # DNS
    dns_qry = str(_first(dns_l.get("dns.qry.name", "")) or "")
    dns_resp = _to_int(_first(dns_l.get("dns.flags.response")), None)

    # HTTP
    http_method = str(_first(http_l.get("http.request.method", "")) or "")
    http_host = str(_first(http_l.get("http.host", "")) or "")
    http_uri = str(_first(http_l.get("http.request.uri", "")) or "")

    # TLS
    tls_handshake = _to_int(_first(tls_l.get("tls.handshake.type")), None)

    protocol = _resolve_protocol(proto_num, protocols, src_port, dst_port)

    record = {
        "event_id": uuid.uuid4().hex[:12],
        "timestamp": ts,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": src_port,
        "dst_port": dst_port,
        "protocol": protocol,
        "packet_length": pkt_len,
        "tcp_flags": tcp_flags_str,
        "tcp_flags_raw": tcp_flags_val,
        "tcp_window": tcp_window,
        "ttl": ttl,
        "icmp_type": icmp_type,
        "icmp_code": icmp_code,
        "dns_query": dns_qry,
        "dns_response": dns_resp,
        "http_method": http_method,
        "http_host": http_host,
        "http_uri": http_uri,
        "tls_handshake_type": tls_handshake,
        "raw_protocols": protocols,
        "source": "tshark",
    }
    return record


def parse_json_array_line(line: str) -> Optional[dict]:
    """Parse one line from tshark -T json streaming output.

    The -T json -l streaming mode outputs JSON objects (each representing a
    single packet) separated by commas within an implicit array, or as
    standalone JSON objects. This parser handles both.
    """
    import json
    text = line.strip()
    if not text:
        return None
    # Strip leading/trailing commas and whitespace (array delimiters)
    text = text.strip().lstrip(",").strip()
    if text in ("[", "]", ""):
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(obj, dict):
        return parse_ek_line(obj)
    return None


def _first(val, default=""):
    """Return first element of list or the value itself."""
    if isinstance(val, list):
        return val[0] if val else default
    return val if val is not None else default


def _to_int(val, default):
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _parse_epoch(ts_val) -> Optional[str]:
    if ts_val is None:
        return None
    try:
        f = float(ts_val)
        return datetime.fromtimestamp(f, timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        return None


def _build_flags_str(tcp_l: dict, flags_val: int) -> str:
    """Build a human-readable TCP flags string."""
    s = str(_first(tcp_l.get("tcp.flags.str", "")))
    if s:
        return s.upper().replace("0x", "")
    parts = []
    if flags_val & 0x01:
        parts.append("F")
    if flags_val & 0x02:
        parts.append("S")
    if flags_val & 0x04:
        parts.append("R")
    if flags_val & 0x08:
        parts.append("P")
    if flags_val & 0x10:
        parts.append("A")
    if flags_val & 0x20:
        parts.append("U")
    return "".join(parts)


def _resolve_protocol(proto_num: int, protocols: str,
                      src_port: int, dst_port: int) -> str:
    """Resolve protocol string from numeric ID and protocol stack."""
    proto_map = {6: "TCP", 17: "UDP", 1: "ICMP", 58: "ICMPV6"}
    if proto_num in proto_map:
        return proto_map[proto_num]
    protos = protocols.lower()
    if "tcp" in protos:
        return "TCP"
    if "udp" in protos:
        return "UDP"
    if "icmp" in protos:
        return "ICMP"
    if "dns" in protos:
        return "DNS"
    return "UNKNOWN"
