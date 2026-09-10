"""
Entity resolution — automatically discovers and tracks network entities.

For every src_ip/dst_ip observed in traffic, an entity is created or updated.
Asset configuration (configs/assets.yaml) can enrich discovered entities with
hostname, type, and criticality metadata.
"""

import ipaddress
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from netwatch.core.events import NetworkEvent

logger = logging.getLogger(__name__)

ENTITY_TYPES = [
    "HOST", "SERVER", "WORKSTATION", "WEB_SERVER", "DATABASE",
    "DNS", "ROUTER", "FIREWALL", "EXTERNAL", "UNKNOWN",
]

CRITICALITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


@dataclass
class NetworkEntity:
    """A resolved network entity (host, server, etc.)."""
    entity_id: str
    ip: str
    hostname: Optional[str] = None
    entity_type: str = "UNKNOWN"
    subnet: Optional[str] = None
    criticality: str = "LOW"
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    packet_count: int = 0
    byte_count: int = 0
    connections: int = 0
    unique_peers: set = field(default_factory=set)
    unique_ports: set = field(default_factory=set)
    syn_count: int = 0
    rst_count: int = 0
    fin_count: int = 0

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "ip": self.ip,
            "hostname": self.hostname,
            "entity_type": self.entity_type,
            "subnet": self.subnet,
            "criticality": self.criticality,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "packet_count": self.packet_count,
            "byte_count": self.byte_count,
            "connections": self.connections,
            "unique_peers": len(self.unique_peers),
            "unique_ports": len(self.unique_ports),
            "syn_count": self.syn_count,
            "rst_count": self.rst_count,
            "fin_count": self.fin_count,
        }

    def update_from_event(self, event: NetworkEvent, is_source: bool):
        """Update entity statistics from an observed event."""
        now = event.timestamp
        if self.first_seen is None or now < self.first_seen:
            self.first_seen = now
        if self.last_seen is None or now > self.last_seen:
            self.last_seen = now
        self.packet_count += 1
        self.byte_count += event.packet_size
        if is_source:
            peer = event.dst_ip
            if event.dst_port:
                self.unique_ports.add(event.dst_port)
        else:
            peer = event.src_ip
            if event.src_port:
                self.unique_ports.add(event.src_port)
        self.unique_peers.add(peer)
        if event.tcp_flags:
            flags = event.tcp_flags.upper()
            if "S" in flags and "A" not in flags:
                self.syn_count += 1
            if "R" in flags:
                self.rst_count += 1
            if "F" in flags:
                self.fin_count += 1


class EntityResolver:
    """Discovers and maintains network entities from observed traffic."""

    def __init__(self, asset_config: Optional[Dict] = None):
        self.entities: Dict[str, NetworkEntity] = {}
        self._asset_config = asset_config or {}
        self._ip_to_entity: Dict[str, str] = {}

    def resolve(self, event: NetworkEvent):
        """Resolve/create entities for both src and dst IPs."""
        src_entity = self._get_or_create(event.src_ip, event.timestamp)
        dst_entity = self._get_or_create(event.dst_ip, event.timestamp)
        src_entity.update_from_event(event, is_source=True)
        dst_entity.update_from_event(event, is_source=False)

    def _get_or_create(self, ip: str, ts: datetime) -> NetworkEntity:
        if ip in self._ip_to_entity:
            return self.entities[self._ip_to_entity[ip]]
        entity_id = f"entity_{ip.replace('.', '_')}"
        subnet = self._detect_subnet(ip)
        asset_info = self._lookup_asset(ip)
        entity = NetworkEntity(
            entity_id=entity_id,
            ip=ip,
            hostname=asset_info.get("hostname"),
            entity_type=asset_info.get("type", self._guess_type(ip)),
            subnet=subnet,
            criticality=asset_info.get("criticality", "LOW"),
            first_seen=ts,
            last_seen=ts,
        )
        self.entities[entity_id] = entity
        self._ip_to_entity[ip] = entity_id
        return entity

    def _detect_subnet(self, ip: str) -> Optional[str]:
        for net_info in self._asset_config.get("networks", []):
            try:
                net = ipaddress.ip_network(net_info["cidr"], strict=False)
                if ipaddress.ip_address(ip) in net:
                    return net_info.get("name", net_info["cidr"])
            except (ValueError, KeyError):
                continue
        return None

    def _lookup_asset(self, ip: str) -> Dict:
        for asset in self._asset_config.get("assets", []):
            if asset.get("ip") == ip:
                return asset
        return {}

    def _guess_type(self, ip: str) -> str:
        if ip.startswith("198.51.100.") or ip.startswith("203.0.113."):
            return "EXTERNAL"
        return "UNKNOWN"

    def get_entity_by_ip(self, ip: str) -> Optional[NetworkEntity]:
        eid = self._ip_to_entity.get(ip)
        return self.entities.get(eid) if eid else None

    def get_all_entities(self) -> List[NetworkEntity]:
        return list(self.entities.values())

    def get_topology(self) -> Dict:
        """Return a summary of discovered entities."""
        return {
            "entity_count": len(self.entities),
            "entities": [e.to_dict() for e in self.entities.values()],
        }
