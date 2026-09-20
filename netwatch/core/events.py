"""
Canonical network event representation.

All input formats (PCAP, CSV, Zeek, NetFlow) are normalized into
NetworkEvent objects before downstream processing. This prevents
downstream modules from depending on a specific input format.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NetworkEvent:
    """A single normalized network event (packet-level or flow-level)."""
    timestamp: datetime

    src_ip: str
    dst_ip: str

    protocol: str

    src_port: Optional[int] = None
    dst_port: Optional[int] = None

    packet_size: int = 0
    payload_size: int = 0

    ttl: Optional[int] = None
    tcp_flags: Optional[str] = None
    tcp_window: Optional[int] = None

    direction: Optional[str] = None

    label: int = 0
    stage: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "protocol": self.protocol,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "packet_size": self.packet_size,
            "payload_size": self.payload_size,
            "ttl": self.ttl,
            "tcp_flags": self.tcp_flags,
            "tcp_window": self.tcp_window,
            "direction": self.direction,
            "label": self.label,
            "stage": self.stage,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "NetworkEvent":
        ts = d.get("timestamp", "")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                ts = datetime.min
        elif isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(ts)
        return cls(
            timestamp=ts,
            src_ip=str(d.get("src_ip", d.get("src", ""))),
            dst_ip=str(d.get("dst_ip", d.get("dst", ""))),
            protocol=str(d.get("protocol", "TCP")).upper(),
            src_port=d.get("src_port"),
            dst_port=d.get("dst_port"),
            packet_size=int(d.get("packet_size", d.get("bytes_sent", d.get("bytes", 0))) or 0),
            payload_size=int(d.get("payload_size", 0) or 0),
            ttl=d.get("ttl"),
            tcp_flags=d.get("tcp_flags", d.get("flags")),
            tcp_window=d.get("tcp_window"),
            direction=d.get("direction"),
            label=int(d.get("label", 0) or 0),
            stage=d.get("stage") or None,
        )
