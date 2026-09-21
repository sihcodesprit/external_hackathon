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
from dataclasses import dataclass
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


def _to_int(value, default: int = 0) -> int:
    """Coerce a CSV/JSON value to int; anything unparsable degrades to default."""
    if value is None or isinstance(value, bool):
        return default if value is None else int(value)
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if not s:
        return default
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return default


def _to_float(value, default: float = 0.0) -> float:
    """Coerce a CSV/JSON value to float; anything unparsable degrades to default."""
    if value is None or isinstance(value, bool):
        return default if value is None else float(value)
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return default
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def normalize_packet_dict(d: Dict) -> Optional[PacketRecord]:
    """Convert an arbitrary dict into a normalized PacketRecord.

    Best-effort: rows with missing or non-numeric fields are still kept with
    safe defaults instead of being dropped, so a flow CSV with one odd column
    can never silently empty the whole capture.
    """
    try:
        return PacketRecord(
            timestamp=str(d.get("timestamp", "")),
            src_ip=str(d.get("src_ip", "") or d.get("src", "")),
            dst_ip=str(d.get("dst_ip", "") or d.get("dst", "")),
            src_port=_to_int(d.get("src_port", 0)),
            dst_port=_to_int(d.get("dst_port", 0)),
            protocol=str(d.get("protocol", "TCP") or "TCP").upper(),
            flags=flags_to_string(d.get("flags")),
            bytes_sent=_to_int(d.get("bytes", d.get("bytes_sent", 0))),
            packets=_to_int(d.get("packets", 1), default=1),
            ttl=_to_int(d.get("ttl", 0)),
            payload_size=_to_int(d.get("payload_size", 0)),
            tcp_window=_to_int(d.get("tcp_window", d.get("tcp_window_size", 0))),
            duration=_to_float(d.get("duration", d.get("flow_duration", 0.0))),
            label=_to_int(d.get("label", 0)),
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


def load_pcap(path: Path, display_name: str | None = None) -> List[PacketRecord]:
    """Load a PCAP file using scapy (optional dependency)."""
    try:
        from scapy.all import rdpcap  # type: ignore
        from scapy.layers.inet import IP, TCP, UDP  # type: ignore
    except ImportError:
        logger.error("scapy not installed — cannot ingest PCAP. Install with: pip install scapy")
        return []

    fname = display_name or Path(path).name
    try:
        pkts = rdpcap(str(path))
    except Exception as e:
        raise ValueError(
            f"Could not read the capture file '{fname}': {e}. "
            "Make sure it is a valid .pcap or .pcapng file."
        ) from e
    if not pkts:
        raise ValueError(f"The capture file '{fname}' contains no packets.")

    records: List[PacketRecord] = []
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

    if not records:
        raise ValueError(
            f"Read {len(pkts)} packets from '{fname}' but none had an IP layer "
            "(only ARP / non-IP link-layer traffic was present). Upload a capture "
            "that contains IPv4/IPv6 traffic, or a flow CSV / JSONL export instead."
        )
    logger.info(f"Loaded {len(records)} packets from PCAP {path}")
    return records


def _decode_csv_text(path: Path) -> str:
    """Decode CSV bytes trying the encodings real-world exports use."""
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-16", "utf-16-le"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _sniff_delimiter(text: str) -> str:
    """Pick the delimiter from the first non-empty data line."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "\t" in line and "," not in line and ";" not in line:
            return "\t"
        if ";" in line and "," not in line:
            return ";"
        return ","
    return ","


def load_flow_csv(path: Path) -> List[PacketRecord]:
    """Load flow records from a CSV (best-effort column mapping).

    Tolerates Excel exports: UTF-8 BOM / UTF-16 encodings, comma / semicolon /
    tab delimiters, whitespace in header names, blank rows, and non-numeric
    values in numeric columns.
    """
    import csv
    import io

    text = _decode_csv_text(path)
    delimiter = _sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    records: List[PacketRecord] = []
    for row in reader:
        if row is None:
            continue
        clean = {
            (k or "").strip(): "" if v is None else v.strip()
            for k, v in row.items()
        }
        if not any(clean.values()):
            continue
        rec = normalize_packet_dict(clean)
        if rec is not None:
            records.append(rec)
    return records


def ingest(path: Path, kind: str = "auto", display_name: str | None = None) -> List[PacketRecord]:
    """Dispatch to the right loader based on file kind."""
    if kind == "pcap" or (kind == "auto" and str(path).lower().endswith((".pcap", ".pcapng"))):
        return load_pcap(path, display_name=display_name)
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
