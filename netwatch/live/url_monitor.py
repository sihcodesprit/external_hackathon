"""URL-target metrics derived from real observed traffic.

Computes URL-specific transmission statistics and feature vectors from a
window of target-filtered events. Everything here is derived ONLY from the
packets that were actually seen on the capture interface.
"""

import logging
import math
import statistics
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _flag_parts(flags: str) -> set:
    return set(str(flags or "").upper())


def is_syn(ev: dict) -> bool:
    parts = _flag_parts(ev.get("tcp_flags"))
    return "S" in parts and "A" not in parts


def is_syn_ack(ev: dict) -> bool:
    parts = _flag_parts(ev.get("tcp_flags"))
    return "S" in parts and "A" in parts


def is_rst(ev: dict) -> bool:
    return "R" in _flag_parts(ev.get("tcp_flags"))


def is_fin(ev: dict) -> bool:
    return "F" in _flag_parts(ev.get("tcp_flags"))


def _shannon_entropy(values) -> float:
    values = [v for v in values if v is not None]
    if not values:
        return 0.0
    counts = Counter(values)
    n = len(values)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def compute_url_metrics(events: List[dict], target, prev: Optional[dict] = None,
                        window_seconds: float = 30.0) -> dict:
    """Compute URL transmission metrics + feature vector for one window.

    events  : target-filtered parsed packet dicts (matching `target`).
    target  : the live UrlTarget being monitored.
    prev    : previous window's metrics dict (for temporal features).
    """
    n = len(events)
    total_bytes = 0
    outbound_packets = 0
    outbound_bytes = 0
    inbound_packets = 0
    inbound_bytes = 0
    syn = syn_ack = ack = rst = fin = 0
    retrans = 0
    tcp_packets = 0
    tls_conn = 0
    sizes = []
    flows = set()
    target_ips_seen = set()
    port_counter = []
    iats = []
    http_requests = 0
    http_responses = 0
    last_ts: Optional[float] = None

    ipset = set(target.current_ips)

    for ev in events:
        length = int(ev.get("packet_length") or 0)
        total_bytes += length
        sizes.append(length)
        proto = str(ev.get("protocol") or "").upper()

        src = str(ev.get("src_ip") or "")
        dst = str(ev.get("dst_ip") or "")
        if src in ipset:
            target_ips_seen.add(src)
        if dst in ipset:
            target_ips_seen.add(dst)

        if proto in ("TCP", "UDP"):
            port_counter.append(ev.get("dst_port"))
            port_counter.append(ev.get("src_port"))

        ts = _ts_float(ev.get("timestamp"))
        if ts is not None and last_ts is not None and ts >= last_ts:
            iats.append(ts - last_ts)
        if ts is not None:
            last_ts = ts

        if target.classify_direction(ev) == "outbound":
            outbound_packets += 1
            outbound_bytes += length
        else:
            inbound_packets += 1
            inbound_bytes += length

        flows.add((src, dst, int(ev.get("src_port") or 0), int(ev.get("dst_port") or 0)))

        if proto == "TCP":
            tcp_packets += 1
            if is_syn(ev):
                syn += 1
            elif is_syn_ack(ev):
                syn_ack += 1
            else:
                ack += 1
            if is_rst(ev):
                rst += 1
            if is_fin(ev):
                fin += 1
            if ev.get("tcp_retransmission"):
                retrans += 1
        if ev.get("tls_handshake_type") is not None:
            tls_conn += 1
        if ev.get("http_method"):
            http_requests += 1
        if ev.get("http_response_code") is not None:
            http_responses += 1

    flow_count = len(flows)
    dest_ip_count = len(target_ips_seen)
    dt = max(window_seconds, 0.001)

    metrics = {
        "packets": n,
        "bytes": total_bytes,
        "flows": flow_count,
        "outbound_packets": outbound_packets,
        "outbound_bytes": outbound_bytes,
        "inbound_packets": inbound_packets,
        "inbound_bytes": inbound_bytes,
        "syn_count": syn,
        "syn_ack_count": syn_ack,
        "ack_count": ack,
        "rst_count": rst,
        "fin_count": fin,
        "retransmissions": retrans,
        "tcp_packets": tcp_packets,
        "tls_connection_count": tls_conn,
        "http_requests": http_requests,
        "http_responses": http_responses,
        "destination_ip_count": dest_ip_count,
        "dns_resolution_count": target.resolution_count,
        "packets_per_second": n / dt,
        "bytes_per_second": total_bytes / dt,
        "connections_rate": syn / dt,
        "upload_rate": outbound_bytes / dt,
        "download_rate": inbound_bytes / dt,
        "average_packet_size": float(statistics.mean(sizes)) if sizes else 0.0,
        "packet_size_variance": float(statistics.pvariance(sizes)) if len(sizes) > 1 else 0.0,
        "packet_size_entropy": _shannon_entropy(sizes),
        "target_port_entropy": _shannon_entropy([p for p in port_counter if p]),
        "iat_mean": float(statistics.mean(iats)) if iats else 0.0,
        "iat_variance": float(statistics.pvariance(iats)) if len(iats) > 1 else 0.0,
        "handshake_ratio": (syn_ack / syn) if syn else 0.0,
        "rst_rate": rst / dt,
        "retransmission_rate": (retrans / tcp_packets) if tcp_packets else 0.0,
        "protocol_distribution": dict(Counter(
            str(ev.get("protocol") or "UNKNOWN").upper() for ev in events)),
    }

    metrics["features"] = {
        "target_packet_count": float(n),
        "target_byte_count": float(total_bytes),
        "target_flow_count": float(flow_count),
        "outbound_packet_count": float(outbound_packets),
        "inbound_packet_count": float(inbound_packets),
        "outbound_byte_count": float(outbound_bytes),
        "inbound_byte_count": float(inbound_bytes),
        "connection_rate": float(syn / dt),
        "target_port_entropy": metrics["target_port_entropy"],
        "target_packet_size_entropy": metrics["packet_size_entropy"],
        "target_IAT_mean": metrics["iat_mean"],
        "target_IAT_variance": metrics["iat_variance"],
        "TCP_handshake_syn": float(syn),
        "TCP_handshake_syn_ack": float(syn_ack),
        "TCP_handshake_ack": float(ack),
        "TCP_handshake_ratio": metrics["handshake_ratio"],
        "RST_rate": metrics["rst_rate"],
        "retransmission_rate": metrics["retransmission_rate"],
        "destination_IP_count": float(dest_ip_count),
        "DNS_resolution_count": float(target.resolution_count),
        "TLS_connection_count": float(tls_conn),
    }
    metrics["destination_ips_seen"] = sorted(target_ips_seen)
    return metrics


def _ts_float(ts) -> Optional[float]:
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None