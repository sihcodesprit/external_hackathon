"""
Dynamic network graph — a real graph abstraction that tracks entities
and their communication over time.

Every observed communication creates/updates:
  - source entity
  - destination entity
  - communication edge with aggregated statistics

The graph supports snapshots for time-series analysis.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GraphNode:
    """A node in the dynamic network graph."""
    entity_id: str
    ip: str
    hostname: Optional[str] = None
    entity_type: str = "UNKNOWN"
    criticality: str = "LOW"
    packet_count: int = 0
    byte_count: int = 0
    degree: int = 0

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "ip": self.ip,
            "hostname": self.hostname,
            "entity_type": self.entity_type,
            "criticality": self.criticality,
            "packet_count": self.packet_count,
            "byte_count": self.byte_count,
            "degree": self.degree,
        }


@dataclass
class GraphEdge:
    """An edge (communication link) in the dynamic network graph."""
    src_id: str
    dst_id: str
    protocols: Set[str] = field(default_factory=set)
    ports: Set[int] = field(default_factory=set)
    packet_count: int = 0
    byte_count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    duration: float = 0.0
    syn_count: int = 0
    syn_ack_count: int = 0
    ack_count: int = 0
    rst_count: int = 0
    fin_count: int = 0
    risk: float = 0.0

    @property
    def edge_key(self) -> str:
        return f"{self.src_id}->{self.dst_id}"

    def to_dict(self) -> dict:
        return {
            "src_id": self.src_id,
            "dst_id": self.dst_id,
            "protocols": list(self.protocols),
            "ports": list(self.ports),
            "packet_count": self.packet_count,
            "byte_count": self.byte_count,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "duration": self.duration,
            "syn_count": self.syn_count,
            "syn_ack_count": self.syn_ack_count,
            "ack_count": self.ack_count,
            "rst_count": self.rst_count,
            "fin_count": self.fin_count,
            "risk": self.risk,
        }


@dataclass
class GraphSnapshot:
    """A point-in-time snapshot of the network graph."""
    timestamp: datetime
    nodes: Dict[str, GraphNode]
    edges: Dict[str, GraphEdge]
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "metadata": self.metadata,
        }


class NetworkGraph:
    """Dynamic network graph that evolves with observed traffic."""

    def __init__(self, max_history: int = 100):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, GraphEdge] = {}
        self.history: List[GraphSnapshot] = []
        self.max_history = max_history

    def add_node(self, entity_id: str, ip: str, hostname: str = None,
                 entity_type: str = "UNKNOWN", criticality: str = "LOW"):
        if entity_id not in self.nodes:
            self.nodes[entity_id] = GraphNode(
                entity_id=entity_id, ip=ip, hostname=hostname,
                entity_type=entity_type, criticality=criticality,
            )

    def add_communication(self, src_id: str, dst_id: str,
                          protocol: str = "TCP", port: int = 0,
                          packet_size: int = 0, timestamp: datetime = None,
                          tcp_flags: str = None):
        """Record a communication between two entities."""
        ek = f"{src_id}->{dst_id}"
        if ek not in self.edges:
            self.edges[ek] = GraphEdge(src_id=src_id, dst_id=dst_id,
                                       first_seen=timestamp)
        edge = self.edges[ek]
        edge.protocols.add(protocol)
        if port:
            edge.ports.add(port)
        edge.packet_count += 1
        edge.byte_count += packet_size
        if timestamp:
            edge.last_seen = timestamp
            if edge.first_seen is None:
                edge.first_seen = timestamp
            edge.duration = (edge.last_seen - edge.first_seen).total_seconds()
        if tcp_flags:
            flags = tcp_flags.upper()
            if "S" in flags and "A" not in flags:
                edge.syn_count += 1
            elif "S" in flags and "A" in flags:
                edge.syn_ack_count += 1
            elif "A" in flags and "S" not in flags:
                edge.ack_count += 1
            if "R" in flags:
                edge.rst_count += 1
            if "F" in flags:
                edge.fin_count += 1

        if src_id in self.nodes:
            self.nodes[src_id].packet_count += 1
            self.nodes[src_id].byte_count += packet_size
        if dst_id in self.nodes:
            self.nodes[dst_id].packet_count += 1
            self.nodes[dst_id].byte_count += packet_size

        self._update_degrees()

    def _update_degrees(self):
        degrees = defaultdict(int)
        for ek, edge in self.edges.items():
            degrees[edge.src_id] += 1
            degrees[edge.dst_id] += 1
        for nid, node in self.nodes.items():
            node.degree = degrees.get(nid, 0)

    def snapshot(self, timestamp: datetime = None) -> GraphSnapshot:
        """Take a point-in-time snapshot of the current graph state."""
        ts = timestamp or datetime.now()
        snap = GraphSnapshot(
            timestamp=ts,
            nodes={k: GraphNode(
                entity_id=n.entity_id, ip=n.ip, hostname=n.hostname,
                entity_type=n.entity_type, criticality=n.criticality,
                packet_count=n.packet_count, byte_count=n.byte_count,
                degree=n.degree,
            ) for k, n in self.nodes.items()},
            edges={k: GraphEdge(
                src_id=e.src_id, dst_id=e.dst_id,
                protocols=set(e.protocols), ports=set(e.ports),
                packet_count=e.packet_count, byte_count=e.byte_count,
                first_seen=e.first_seen, last_seen=e.last_seen,
                duration=e.duration, syn_count=e.syn_count,
                syn_ack_count=e.syn_ack_count, ack_count=e.ack_count,
                rst_count=e.rst_count, fin_count=e.fin_count, risk=e.risk,
            ) for k, e in self.edges.items()},
            metadata={
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
            },
        )
        self.history.append(snap)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        return snap

    def compute_topology_delta(self) -> Dict:
        """Compute changes since the last snapshot."""
        if len(self.history) < 2:
            return {
                "new_nodes": 0, "removed_nodes": 0,
                "new_edges": 0, "removed_edges": 0,
                "new_destinations": 0, "new_sources": 0,
            }
        prev = self.history[-2]
        curr = self.history[-1]
        prev_nodes = set(prev.nodes.keys())
        curr_nodes = set(curr.nodes.keys())
        prev_edges = set(prev.edges.keys())
        curr_edges = set(curr.edges.keys())
        return {
            "new_nodes": len(curr_nodes - prev_nodes),
            "removed_nodes": len(prev_nodes - curr_nodes),
            "new_edges": len(curr_edges - prev_edges),
            "removed_edges": len(prev_edges - curr_edges),
            "new_destinations": len(curr_nodes - prev_nodes),
            "new_sources": len(curr_nodes - prev_nodes),
        }

    def get_node_stats(self, entity_id: str) -> Optional[Dict]:
        node = self.nodes.get(entity_id)
        return node.to_dict() if node else None

    def get_edge_stats(self, src_id: str, dst_id: str) -> Optional[Dict]:
        ek = f"{src_id}->{dst_id}"
        edge = self.edges.get(ek)
        return edge.to_dict() if edge else None

    def get_all_edges(self) -> List[Dict]:
        return [e.to_dict() for e in self.edges.values()]

    def get_all_nodes(self) -> List[Dict]:
        return [n.to_dict() for n in self.nodes.values()]

    def get_topology(self) -> Dict:
        return {
            "nodes": self.get_all_nodes(),
            "edges": self.get_all_edges(),
            "counts": {"nodes": len(self.nodes), "edges": len(self.edges)},
        }
