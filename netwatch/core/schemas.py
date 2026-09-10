"""
Shared schema definitions for the NetWatch platform.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EntityInfo:
    """Metadata about a network entity."""
    entity_id: str
    ip: str
    hostname: Optional[str] = None
    entity_type: str = "UNKNOWN"
    subnet: Optional[str] = None
    criticality: str = "LOW"


@dataclass
class EdgeInfo:
    """Metadata about a communication edge."""
    src_entity: str
    dst_entity: str
    protocol: str = "TCP"
    ports: List[int] = field(default_factory=list)
    packet_count: int = 0
    byte_count: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    duration: float = 0.0
    syn_count: int = 0
    syn_ack_count: int = 0
    ack_count: int = 0
    rst_count: int = 0
    fin_count: int = 0
    risk: float = 0.0


@dataclass
class ForecastStep:
    """A single step in a K-step forecast."""
    step: int
    window: str
    risk: float
    stage: str
    stage_probability: float
    confidence: float
    state_vec: List[float] = field(default_factory=list)
    features: Dict[str, float] = field(default_factory=dict)
