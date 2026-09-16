"""Convert parsed TShark event dicts into canonical PacketRecord objects."""

import logging
from typing import Optional

from netwatch.ingestion.parser import PacketRecord, flags_to_string

logger = logging.getLogger(__name__)


def event_to_packet_record(event: dict) -> Optional[PacketRecord]:
    """Convert a parsed TShark event dict to a normalized PacketRecord."""
    if not event or not event.get("src_ip"):
        return None
    try:
        return PacketRecord(
            timestamp=event.get("timestamp", ""),
            src_ip=str(event.get("src_ip", "")),
            dst_ip=str(event.get("dst_ip", "")),
            src_port=int(event.get("src_port", 0) or 0),
            dst_port=int(event.get("dst_port", 0) or 0),
            protocol=str(event.get("protocol", "TCP") or "TCP").upper(),
            flags=flags_to_string(event.get("tcp_flags", "")),
            bytes_sent=int(event.get("packet_length", 0) or 0),
            packets=1,
            ttl=int(event.get("ttl") or 0),
            payload_size=max(0, int(event.get("packet_length", 0) or 0) - 40),
            tcp_window=int(event.get("tcp_window") or 0),
            duration=0.0,
            label=0,
            stage="",
        )
    except Exception as e:
        logger.debug("Failed to normalize event: %s", e)
        return None