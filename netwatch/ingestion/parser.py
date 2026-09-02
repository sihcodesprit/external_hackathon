"""
Packet and flow ingestion.

Turns raw telemetry (packet dicts from JSONL, PCAP via scapy when available,
or CSV flow records) into normalized packet/flow records ready for
feature extraction. A normalized record contains:

    timestamp, src_ip, dst_ip, src_port, dst_port, protocol,
    flags, bytes, packets, ttl, payload_size, tcp_window, duration

This module is fully self-contained and does NOT depend on external
submodules. scapy is optional and only used for live/PCAP ingestion.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PacketRecord:
    """A single normalized packet / flow observation."""
    timestamp: str
    src_ip: str = ""
    dst_ip: str = ""
    src_port: int = 0
    dst_port: int = 0
    protocol: str = "TCP"
    flags: str = ""
    bytes_sent: int = 0
    packets: int = 1
    ttl: int = 0
    payload_size: int = 0
    tcp_window: int = 0
    duration: float = 0.0
    label: int = 0                # 0 = benign, 1 = attack (ground truth when known)
    stage: str = ""               # optional MITRE stage ground truth


def _parse_ts(ts_str: str) -> Optional[datetime]:
    """Parse an ISO timestamp robustly."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
    except Exception:
        return None


def flags_to_string(flags) -> str:
    """Normalize TCP flags to a canonical string (subset used downstream)."""
    if flags is None:
        return ""
    if isinstance(flags, str):
        # Already a string like "SA" — uppercase, strip
        return "".join(sorted(set(f.upper() for f in flags if f.isalpha())))
    # Scapy / int bitmask
    try:
        v = int(flags)
        parts = []
        if v & 0x01:
            parts.append("F")
        if v & 0x02:
            parts.append("S")
        if v & 0x04:
            parts.append("R")
        if v & 0x08:
            parts.append("P")
        if v & 0x10:
            parts.append("A")
        return "".join(parts)
    except Exception:
        return ""


def normalize_packet_dict(d: Dict) -> Optional[PacketRecord]:
    """Convert an arbitrary dict into a normalized PacketRecord."""
    try:
        return PacketRecord(
            timestamp=str(d.get("timestamp", "")),
            src_ip=str(d.get("src_ip", "") or d.get("src", "")),
            dst_ip=str(d.get("dst_ip", "") or d.get("dst", "")),
            src_port=int(d.get("src_port", 0) or 0),
            dst_port=int(d.get("dst_port", 0) or 0),
            protocol=str(d.get("protocol", "TCP") or "TCP").upper(),
            flags=flags_to_string(d.get("flags")),
            bytes_sent=int(d.get("bytes", d.get("bytes_sent", 0)) or 0),
            packets=int(d.get("packets", 1) or 1),
            ttl=int(d.get("ttl", 0) or 0),
            payload_size=int(d.get("payload_size", 0) or 0),
            tcp_window=int(d.get("tcp_window", d.get("tcp_window_size", 0)) or 0),
            duration=float(d.get("duration", d.get("flow_duration", 0.0)) or 0.0),
            label=int(d.get("label", 0) or 0),
            stage=str(d.get("stage", "") or ""),
        )
    except Exception as e:
        logger.debug(f"Failed to normalize packet dict: {e}")
        return None


def load_packets_jsonl(path: Path) -> List[PacketRecord]:
    """Load normalized packet records from a JSONL file (or JSON array)."""
    records: List[PacketRecord] = []
    if not Path(path).exists():
        return records
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return records
    rows: List[Dict] = []
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            rows = parsed
        elif isinstance(parsed, dict):
            rows = [parsed]
    except json.JSONDecodeError:
        for line in content.splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    for r in rows:
        rec = normalize_packet_dict(r)
        if rec is not None:
            records.append(rec)
    return records


def load_pcap(path: Path) -> List[PacketRecord]:
    """Load a PCAP file using scapy (optional dependency)."""
    try:
        from scapy.all import rdpcap  # type: ignore
        from scapy.layers.inet import IP, TCP, UDP  # type: ignore
    except ImportError:
        logger.error("scapy not installed — cannot ingest PCAP. Install with: pip install scapy")
        return []

    records: List[PacketRecord] = []
    pkts = rdpcap(str(path))
    for pkt in pkts:
        if not pkt.haslayer(IP):
            continue
        ip = pkt["IP"]
        rec = PacketRecord(
            timestamp=pkt.time if isinstance(pkt.time, str) else str(pkt.time),
            src_ip=ip.src,
            dst_ip=ip.dst,
            protocol={6: "TCP", 17: "UDP", 1: "ICMP"}.get(ip.proto, str(ip.proto)),
            ttl=int(ip.ttl),
        )
        if pkt.haslayer(TCP):
            tcp = pkt["TCP"]
            rec.src_port = int(tcp.sport)
            rec.dst_port = int(tcp.dport)
            rec.flags = flags_to_string(int(tcp.flags))
            rec.payload_size = len(tcp.payload)
            rec.tcp_window = int(tcp.window)
        elif pkt.haslayer(UDP):
            udp = pkt["UDP"]
            rec.src_port = int(udp.sport)
            rec.dst_port = int(udp.dport)
            rec.payload_size = len(udp.payload)
        rec.bytes_sent = len(pkt)
        records.append(rec)
    logger.info(f"Loaded {len(records)} packets from PCAP {path}")
    return records


def load_flow_csv(path: Path) -> List[PacketRecord]:
    """Load flow records from a CSV (best-effort column mapping)."""
    import csv

    records: List[PacketRecord] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec = normalize_packet_dict(row)
            if rec is not None:
                records.append(rec)
    return records


def ingest(path: Path, kind: str = "auto") -> List[PacketRecord]:
    """Dispatch to the right loader based on file kind."""
    if kind == "pcap" or (kind == "auto" and str(path).lower().endswith((".pcap", ".pcapng"))):
        return load_pcap(path)
    if kind == "csv" or (kind == "auto" and str(path).lower().endswith(".csv")):
        return load_flow_csv(path)
    return load_packets_jsonl(path)


def iter_records(records: Iterable[PacketRecord]) -> Iterable[Dict]:
    """Yield records as plain dicts for serialization."""
    for r in records:
        yield {
            "timestamp": r.timestamp,
            "src_ip": r.src_ip,
            "dst_ip": r.dst_ip,
            "src_port": r.src_port,
            "dst_port": r.dst_port,
            "protocol": r.protocol,
            "flags": r.flags,
            "bytes": r.bytes_sent,
            "packets": r.packets,
            "ttl": r.ttl,
            "payload_size": r.payload_size,
            "tcp_window": r.tcp_window,
            "duration": r.duration,
            "label": r.label,
            "stage": r.stage,
        }
