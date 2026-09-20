"""Live flow tracking from NetworkEvents / PacketRecords."""

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class Flow:
    flow_id: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    packet_count: int = 0
    byte_count: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    duration: float = 0.0
    syn_count: int = 0
    syn_ack_count: int = 0
    ack_count: int = 0
    rst_count: int = 0
    fin_count: int = 0
    inbound_packets: int = 0
    outbound_packets: int = 0
    inbound_bytes: int = 0
    outbound_bytes: int = 0

    def to_dict(self) -> dict:
        return {
            "flow_id": self.flow_id,
            "src_ip": self.src_ip, "dst_ip": self.dst_ip,
            "src_port": self.src_port, "dst_port": self.dst_port,
            "protocol": self.protocol,
            "packet_count": self.packet_count, "byte_count": self.byte_count,
            "first_seen": self.first_seen, "last_seen": self.last_seen,
            "duration": self.duration,
            "syn_count": self.syn_count, "syn_ack_count": self.syn_ack_count,
            "ack_count": self.ack_count, "rst_count": self.rst_count,
            "fin_count": self.fin_count,
        }


class FlowTracker:
    """Tracks live flows with bounded memory."""

    def __init__(self, max_flows: int = 5000, flow_timeout: float = 300.0):
        self._flows: Dict[str, Flow] = {}
        self._flow_keys: Dict[tuple, str] = {}
        self._max_flows = max_flows
        self._flow_timeout = flow_timeout
        self._hosts_seen: Set[str] = set()
        self._total_flows_created = 0

    def process_event(self, event: dict) -> Optional[Flow]:
        """Process a normalized event dict and update flow tracking."""
        src_ip = event.get("src_ip", "")
        dst_ip = event.get("dst_ip", "")
        if not src_ip or not dst_ip:
            return None

        key = (src_ip, dst_ip,
               int(event.get("src_port", 0) or 0),
               int(event.get("dst_port", 0) or 0),
               str(event.get("protocol", "TCP")).upper())

        if key in self._flow_keys:
            flow_id = self._flow_keys[key]
            flow = self._flows.get(flow_id)
            if flow is None:
                flow_id = self._make_flow_id(key)
                flow = self._create_flow(key, flow_id, event)
            self._update_flow(flow, event)
            return flow

        if len(self._flows) >= self._max_flows:
            self._evict_oldest()

        flow_id = self._make_flow_id(key)
        flow = self._create_flow(key, flow_id, event)
        self._update_flow(flow, event)
        return flow

    def _create_flow(self, key: tuple, flow_id: str, event: dict) -> Flow:
        now = time.time()
        flow = Flow(
            flow_id=flow_id,
            src_ip=key[0], dst_ip=key[1],
            src_port=key[2], dst_port=key[3],
            protocol=key[4],
            first_seen=now, last_seen=now,
        )
        self._flows[flow_id] = flow
        self._flow_keys[key] = flow_id
        self._total_flows_created += 1
        self._hosts_seen.add(key[0])
        self._hosts_seen.add(key[1])
        return flow

    def _update_flow(self, flow: Flow, event: dict):
        now = time.time()
        flow.last_seen = now
        flow.duration = now - flow.first_seen
        pkt_len = int(event.get("packet_length", 0) or 0)
        flow.packet_count += 1
        flow.byte_count += pkt_len
        flags = str(event.get("tcp_flags", "")).upper()
        if "S" in flags and "A" not in flags:
            flow.syn_count += 1
        if "S" in flags and "A" in flags:
            flow.syn_ack_count += 1
        if "A" in flags and "S" not in flags:
            flow.ack_count += 1
        if "R" in flags:
            flow.rst_count += 1
        if "F" in flags:
            flow.fin_count += 1

    def _make_flow_id(self, key: tuple) -> str:
        return f"{key[0]}:{key[2]}->{key[1]}:{key[3]}:{key[4]}"

    def _evict_oldest(self):
        if not self._flows:
            return
        oldest_id = min(self._flows, key=lambda k: self._flows[k].last_seen)
        flow = self._flows.pop(oldest_id, None)
        if flow:
            key = (flow.src_ip, flow.dst_ip, flow.src_port, flow.dst_port, flow.protocol)
            self._flow_keys.pop(key, None)

    def get_stats(self) -> dict:
        now = time.time()
        active = 0
        for f in self._flows.values():
            if now - f.last_seen < self._flow_timeout:
                active += 1
        return {
            "total_flows": self._total_flows_created,
            "active_flows": active,
            "hosts_seen": len(self._hosts_seen),
        }

    def get_current_flows(self) -> list:
        return [f.to_dict() for f in self._flows.values()]

    def reset(self):
        self._flows.clear()
        self._flow_keys.clear()
        self._hosts_seen.clear()
        self._total_flows_created = 0
