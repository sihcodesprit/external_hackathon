"""
NetworkState representation.

Each time window is represented as a structured state vector S_t containing
flow, packet, and temporal features. States are what the World Model consumes.

The canonical feature vector is defined by config.FEATURE_COLUMNS. Numerical
features are normalized during dataset construction; NetworkState itself carries
raw (unnormalized) values plus the timestamp.
"""

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from main.netwatch.config import FEATURE_COLUMNS, WINDOW_SECONDS, WINDOW_STEP_SECONDS
from main.netwatch.ingestion.parser import PacketRecord

# Canonical feature vector keys (order matters for the model)
FLOW_FEATURES = ["bytes", "packets"]
PACKET_FEATURES = ["ttl_mean", "payload_mean", "payload_max", "tcp_window_mean"]
TEMPORAL_FEATURES = [
    "packets_per_second", "connection_rate", "unique_dst_ports", "unique_dst_hosts",
    "syn_rate", "ack_rate", "rst_rate", "syn_ack_ratio", "port_entropy",
]


def _parse_ts(ts_str: str) -> Optional[datetime]:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
    except Exception:
        return None


def port_entropy(ports: List[int]) -> float:
    """Shannon entropy of a port distribution — high for random/sweep scans."""
    if not ports:
        return 0.0
    counts: Dict[int, int] = defaultdict(int)
    for p in ports:
        counts[p] += 1
    total = float(len(ports))
    e = 0.0
    for c in counts.values():
        p = c / total
        e -= p * math.log2(p)
    return e


def compute_window_features(pkts: List[PacketRecord]) -> Dict[str, float]:
    """Aggregate a list of PacketRecords into a feature vector (unnormalized)."""
    total = len(pkts)
    duration = max(WINDOW_SECONDS, 1.0)

    # Build individual feature lists for statistics
    ttls, payloads, windows = [], [], []
    ports: List[int] = []
    dst_hosts: set = set()
    syn = ack = rst = 0

    for p in pkts:
        ttls.append(p.ttl)
        payloads.append(p.payload_size)
        windows.append(p.tcp_window)
        if p.dst_port:
            ports.append(p.dst_port)
        if p.dst_ip:
            dst_hosts.add(p.dst_ip)
        f = p.flags.upper()
        if "S" in f and "A" not in f:
            syn += 1
        if "A" in f:
            ack += 1
        if "R" in f:
            rst += 1

    syn_rate = syn / duration
    ack_rate = ack / duration
    rst_rate = rst / duration
    syn_ack_ratio = syn / max(ack, 1)

    features: Dict[str, float] = {
        "bytes": float(sum(p.bytes_sent for p in pkts)),
        "packets": float(total),
        "ttl_mean": statistics.mean(ttls) if ttls else 0.0,
        "payload_mean": statistics.mean(payloads) if payloads else 0.0,
        "payload_max": float(max(payloads)) if payloads else 0.0,
        "tcp_window_mean": statistics.mean(windows) if windows else 0.0,
        "packets_per_second": total / duration,
        "connection_rate": total / duration,
        "unique_dst_ports": float(len(set(ports))),
        "unique_dst_hosts": float(len(dst_hosts)),
        "syn_rate": syn_rate,
        "ack_rate": ack_rate,
        "rst_rate": rst_rate,
        "syn_ack_ratio": syn_ack_ratio,
        "port_entropy": port_entropy(ports),
    }
    return features


@dataclass
class NetworkState:
    """A timestamped window of network activity with an embedded feature vector."""
    timestamp: str
    features: Dict[str, float] = field(default_factory=dict)
    src_ip: str = ""
    dst_ip: str = ""
    label: Optional[int] = None       # optional ground-truth attack indicator
    stage: Optional[str] = None       # optional ground-truth / predicted MITRE stage

    def vector(self, columns: Optional[List[str]] = None) -> List[float]:
        cols = columns or FEATURE_COLUMNS
        return [self.features.get(c, 0.0) for c in cols]

    def to_dict(self) -> Dict:
        d = dict(self.features)
        d["timestamp"] = self.timestamp
        d["src_ip"] = self.src_ip
        d["dst_ip"] = self.dst_ip
        if self.label is not None:
            d["label"] = self.label
        if self.stage is not None:
            d["stage"] = self.stage
        return d


class StateBuilder:
    """
    Builds a temporal sequence of NetworkState objects from packet records by
    sliding a window over time, grouped (optionally) per (src, dst) pair.
    """

    def __init__(self, window_seconds: int = WINDOW_SECONDS,
                 window_step: int = WINDOW_STEP_SECONDS,
                 group_by_pair: bool = True):
        self.window_seconds = window_seconds
        self.window_step = window_step
        self.group_by_pair = group_by_pair

    def build_states(self, records: List[PacketRecord]) -> List[NetworkState]:
        if not records:
            return []

        if self.group_by_pair:
            groups: Dict[tuple, List[PacketRecord]] = defaultdict(list)
            for r in records:
                groups[(r.src_ip, r.dst_ip)].append(r)
        else:
            groups = {("", ""): records}

        states: List[NetworkState] = []
        for (src, dst), pkts in groups.items():
            # Keep only packets we can timestamp, sorted ascending.
            timed = []
            for r in pkts:
                ts = _parse_ts(r.timestamp)
                if ts is not None:
                    timed.append((ts, r))
            if not timed:
                continue
            timed.sort(key=lambda x: x[0])

            first = timed[0][0]
            last = timed[-1][0]
            win_start = first
            # Sliding window via two pointers over the sorted packets (O(n)).
            i = 0
            n = len(timed)
            while win_start <= last:
                win_end = win_start + timedelta(seconds=self.window_seconds)
                # advance the right pointer
                while i < n and timed[i][0] < win_end:
                    i += 1
                # advance the left pointer past windows we've consumed
                j = i
                while j > 0 and timed[j - 1][0] >= win_start:
                    j -= 1
                window_pkts = [timed[k][1] for k in range(j, i)]
                if window_pkts:
                    feats = compute_window_features(window_pkts)
                    # derive ground-truth label/stage from packets in the window
                    attack_count = sum(1 for p in window_pkts if p.label == 1)
                    label = 1 if attack_count >= max(1, int(0.2 * len(window_pkts))) else 0
                    stage = ""
                    if label:
                        # most common ground-truth stage among attack packets
                        stage = max(
                            [p.stage for p in window_pkts if p.label == 1 and p.stage],
                            default="",
                        )
                    states.append(NetworkState(
                        timestamp=win_start.isoformat().replace("+00:00", "Z"),
                        features=feats,
                        src_ip=src,
                        dst_ip=dst,
                        label=label,
                        stage=stage or None,
                    ))
                win_start += timedelta(seconds=self.window_step)

        states.sort(key=lambda s: s.timestamp)
        return states
