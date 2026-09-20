"""
NetworkState representation.

Each time window is represented as a structured state vector S_t containing
flow, packet, and temporal features. States are what the World Model consumes.

The canonical feature vector is defined by the FeatureRegistry. Numerical
features are normalized during dataset construction; NetworkState itself carries
raw (unnormalized) values plus the timestamp.
"""

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from netwatch.config import (
    WINDOW_SECONDS,
    WINDOW_STEP_SECONDS,
    get_feature_columns,
)
from netwatch.features.baseline_features import BaselineTracker, compute_baseline_features
from netwatch.features.entropy_features import compute_entropy_features
from netwatch.features.graph_features import DynamicGraph, compute_graph_features
from netwatch.features.tcp_features import compute_tcp_handshake_features
from netwatch.features.temporal_features import compute_temporal_features
from netwatch.features.trajectory_features import TrajectoryTracker, compute_trajectory_features
from netwatch.ingestion.parser import PacketRecord

# Legacy feature group names for backward compatibility
FLOW_FEATURES = ["bytes", "packets"]
PACKET_FEATURES = ["ttl_mean", "payload_mean", "payload_max", "tcp_window_mean"]
TEMPORAL_FEATURES = [
    "packets_per_second", "connection_rate", "unique_dst_ports", "unique_dst_hosts",
    "syn_rate", "ack_rate", "rst_rate", "syn_ack_ratio", "port_entropy",
]


def _parse_ts(ts_str: str) -> Optional[datetime]:
    if not ts_str:
        return None
    if isinstance(ts_str, datetime):
        return ts_str
    s = str(ts_str).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    try:
        return datetime.fromtimestamp(float(s))
    except (ValueError, OverflowError, OSError):
        return None


def compute_base_features(pkts: List[PacketRecord], actual_window_seconds: float = None) -> Dict[str, float]:
    """Compute basic flow, packet, and temporal features (original implementation)."""
    total = len(pkts)
    duration = actual_window_seconds if actual_window_seconds and actual_window_seconds > 0 else max(WINDOW_SECONDS, 1.0)

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

    payload_mean = statistics.mean(payloads) if payloads else 0.0
    payload_max = float(max(payloads)) if payloads else 0.0
    tcp_window_mean = statistics.mean(windows) if windows else 0.0
    packets_per_second = total / duration
    port_entropy = _port_entropy(ports)
    total_bytes = float(sum(p.bytes_sent for p in pkts))

    features: Dict[str, float] = {
        "bytes": total_bytes,
        "packets": float(total),
        "ttl_mean": statistics.mean(ttls) if ttls else 0.0,
        "payload_mean": payload_mean,
        "payload_max": payload_max,
        "tcp_window_mean": tcp_window_mean,
        "packets_per_second": packets_per_second,
        "connection_rate": packets_per_second,
        "unique_dst_ports": float(len(set(ports))),
        "unique_dst_hosts": float(len(dst_hosts)),
        "syn_rate": syn_rate,
        "ack_rate": ack_rate,
        "rst_rate": rst_rate,
        "syn_ack_ratio": syn_ack_ratio,
        "port_entropy": port_entropy,
    }
    # Mirror names used by the world-model feature vector (get_feature_columns)
    # so state vectors carry real magnitudes for these features.
    features.update({
        "payload_size_mean": payload_mean,
        "payload_size_max": payload_max,
        "packet_rate": packets_per_second,
        "byte_rate": total_bytes / duration,
        "flow_rate": packets_per_second,
        "total_packets": float(total),
        "total_bytes": total_bytes,
        "average_packet_size": (total_bytes / total) if total else 0.0,
        "dst_port_entropy": port_entropy,
    })
    return features


def _port_entropy(ports: List[int]) -> float:
    """Shannon entropy of a port distribution."""
    if not ports:
        return 0.0
    counts: Dict[int, int] = defaultdict(int)
    for p in ports:
        counts[p] += 1
    total = float(len(ports))
    e = 0.0
    import math
    for c in counts.values():
        p = c / total
        e -= p * math.log2(p) if p > 0 else 0
    return e


def _packet_records_to_dicts(pkts: List[PacketRecord]) -> List[Dict]:
    """Convert PacketRecord objects to dicts for feature modules."""
    return [
        {
            "timestamp": p.timestamp,
            "src_ip": p.src_ip,
            "dst_ip": p.dst_ip,
            "src_port": p.src_port,
            "dst_port": p.dst_port,
            "protocol": p.protocol,
            "flags": p.flags,
            "bytes_sent": p.bytes_sent,
            "packets": p.packets,
            "ttl": p.ttl,
            "payload_size": p.payload_size,
            "tcp_window": p.tcp_window,
            "duration": p.duration,
            "label": p.label,
            "stage": p.stage,
        }
        for p in pkts
    ]


@dataclass
class NetworkState:
    """A timestamped window of network activity with an embedded feature vector."""
    timestamp: str
    features: Dict[str, float] = field(default_factory=dict)
    src_ip: str = ""
    dst_ip: str = ""
    label: Optional[int] = None
    stage: Optional[str] = None

    def vector(self, columns: Optional[List[str]] = None) -> List[float]:
        cols = columns or get_feature_columns()
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

    Adaptive windowing: If the total duration of the capture is shorter than
    the default window, it scales down automatically so that ANY size PCAP
    will produce valid state sequences (minimum 1-second windows, at least 2
    windows per group, with overlap via step scaling).
    """

    MIN_WINDOW_SECONDS = 1.0
    MIN_WINDOW_STEP = 1.0
    MIN_WINDOWS_DESIRED = 5
    # Packet-bucket fallback: any group with at least a few packets yields a
    # trainable state sequence even when timestamps are all identical (the
    # training sequence length adapts down to fit the capture size).
    PACKET_BUCKET_MIN_PACKETS = 3
    PACKET_BUCKET_TARGET = 14

    def __init__(self,
                 window_seconds: int = WINDOW_SECONDS,
                 window_step: int = WINDOW_STEP_SECONDS,
                 group_by_pair: bool = True,
                 enable_advanced_features: bool = True):
        self.window_seconds = window_seconds
        self.window_step = window_step
        self.group_by_pair = group_by_pair
        self.enable_advanced_features = enable_advanced_features

        # State for temporal features
        self._entropy_history: List[Dict] = []
        self._handshake_history: List[Dict] = []
        self._graph_state: Optional[DynamicGraph] = None
        self._trajectory_tracker: Optional[TrajectoryTracker] = None
        self._baseline_tracker: Optional[BaselineTracker] = None

    def _adapt_window(self, total_duration: float, n_packets: int) -> tuple:
        """Compute adaptive window size and step based on capture duration.

        Returns (window_seconds, window_step).
        """
        ws = self.window_seconds
        step = self.window_step

        if total_duration <= 0 or n_packets < 2:
            return (self.MIN_WINDOW_SECONDS, self.MIN_WINDOW_STEP)

        # If capture is shorter than the configured window, scale down
        if total_duration < ws:
            # Target: produce at least MIN_WINDOWS_DESIRED windows
            # window = total_duration / (MIN_WINDOWS_DESIRED - 1) or just total_duration / 2
            target_ws = max(self.MIN_WINDOW_SECONDS, total_duration / max(self.MIN_WINDOWS_DESIRED, 2))
            # Clamp to actual duration so at least 2 packets per window
            ws = max(self.MIN_WINDOW_SECONDS, min(target_ws, total_duration))
            # Step = window / 2 for 50% overlap, but never below MIN_WINDOW_STEP
            step = max(self.MIN_WINDOW_STEP, ws / 2.0)
        else:
            # Even for longer captures, ensure we get enough windows
            n_windows_est = (total_duration - ws) / max(step, 1) + 1
            if n_windows_est < self.MIN_WINDOWS_DESIRED and total_duration > self.MIN_WINDOW_SECONDS:
                # Reduce window slightly to produce more windows
                ws = max(self.MIN_WINDOW_SECONDS, total_duration / self.MIN_WINDOWS_DESIRED)
                step = max(self.MIN_WINDOW_STEP, ws / 2.0)

        # Final guard: never exceed total_duration for window
        ws = min(ws, total_duration)
        return (ws, step)

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

        # Reset temporal state for new build
        self._entropy_history = []
        self._handshake_history = []
        self._graph_state = None
        self._trajectory_tracker = None
        self._baseline_tracker = None

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

            # Convert to dicts once per group
            pkt_dicts = _packet_records_to_dicts([p for _, p in timed])

            group_states = self._build_time_window_states(timed, pkt_dicts, src, dst)

            # Degenerate-timestamp fallback: a capture whose packets all share
            # the same second (or look instantaneous) collapses the time-window
            # slide into 1-2 windows, which can never form a training sequence.
            # Split the group into contiguous packet buckets with synthetic
            # 1-second spacing so ANY sufficiently large capture still yields a
            # trainable state sequence instead of failing with "not enough
            # windows" downstream.
            if (
                len(group_states) < self.MIN_WINDOWS_DESIRED
                and len(timed) >= self.PACKET_BUCKET_MIN_PACKETS
            ):
                group_states = self._build_packet_bucket_states(
                    timed, pkt_dicts, src, dst
                )

            states.extend(group_states)

        states.sort(key=lambda s: s.timestamp)
        return states

    def _build_time_window_states(
        self,
        timed: List[tuple],
        pkt_dicts: List[Dict],
        src: str,
        dst: str,
    ) -> List[NetworkState]:
        """Slide a time window (with adaptive sizing for short captures)."""
        first = timed[0][0]
        last = timed[-1][0]
        total_duration = (last - first).total_seconds()

        ws, step = self._adapt_window(total_duration, len(timed))

        out: List[NetworkState] = []
        win_start = first
        i = 0
        n = len(timed)

        while win_start <= last:
            win_end = win_start + timedelta(seconds=ws)
            while i < n and timed[i][0] < win_end:
                i += 1
            j = i
            while j > 0 and timed[j - 1][0] >= win_start:
                j -= 1

            window_pkts = [timed[k][1] for k in range(j, i)]
            window_dicts = pkt_dicts[j:i]

            st = self._build_state(window_pkts, window_dicts, win_start, src, dst, ws)
            if st:
                out.append(st)

            win_start += timedelta(seconds=step)

        return out

    def _build_packet_bucket_states(
        self,
        timed: List[tuple],
        pkt_dicts: List[Dict],
        src: str,
        dst: str,
    ) -> List[NetworkState]:
        """Fallback for degenerate timestamps: contiguous packet buckets with
        synthetic 1-second spacing, sized to yield ~PACKET_BUCKET_TARGET states."""
        n = len(timed)
        bucket_size = max(1, math.ceil(n / self.PACKET_BUCKET_TARGET))
        first = timed[0][0]

        out: List[NetworkState] = []
        idx = 0
        bucket_index = 0
        while idx < n:
            chunk = timed[idx: idx + bucket_size]
            if chunk:
                win_start = first + timedelta(seconds=bucket_index)
                st = self._build_state(
                    [r for _, r in chunk],
                    pkt_dicts[idx: idx + bucket_size],
                    win_start,
                    src,
                    dst,
                    1.0,
                )
                if st:
                    out.append(st)
            idx += bucket_size
            bucket_index += 1

        return out

    def _build_state(
        self,
        window_pkts: List[PacketRecord],
        window_dicts: List[Dict],
        win_start: datetime,
        src: str,
        dst: str,
        window_seconds: float,
    ) -> Optional[NetworkState]:
        """Compute the full feature vector and ground-truth for one window."""
        if not window_pkts:
            return None

        feats = compute_base_features(window_pkts, actual_window_seconds=window_seconds)

        if self.enable_advanced_features:
            # Entropy features with temporal derivatives
            entropy_feats = compute_entropy_features(
                window_dicts,
                self._entropy_history[-1] if self._entropy_history else None,
                self._entropy_history[-2] if len(self._entropy_history) >= 2 else None
            )
            feats.update(entropy_feats)
            self._entropy_history.append(entropy_feats)

            # TCP handshake features
            handshake_feats = compute_tcp_handshake_features(
                window_dicts,
                self._handshake_history[-1] if self._handshake_history else None
            )
            feats.update(handshake_feats)
            self._handshake_history.append(handshake_feats)

            # Temporal/jitter features
            temporal_feats = compute_temporal_features(window_dicts)
            feats.update(temporal_feats)

            # Graph features
            graph_feats, self._graph_state = compute_graph_features(
                window_dicts, self._graph_state
            )
            feats.update(graph_feats)

            # Initialize trackers on first window
            if self._trajectory_tracker is None:
                self._trajectory_tracker = TrajectoryTracker()
            if self._baseline_tracker is None:
                self._baseline_tracker = BaselineTracker()

            # Trajectory features
            trajectory_feats, self._trajectory_tracker = compute_trajectory_features(
                feats, self._trajectory_tracker
            )
            feats.update(trajectory_feats)

            # Baseline deviation features
            is_benign = not any(p.label == 1 for p in window_pkts)
            baseline_feats, self._baseline_tracker = compute_baseline_features(
                feats, self._baseline_tracker, is_benign=is_benign
            )
            feats.update(baseline_feats)

        # Derive ground-truth label/stage (majority vote per window so
        # mixed captures produce both attack and benign windows)
        attack_count = sum(1 for p in window_pkts if p.label == 1)
        label = 1 if attack_count * 2 >= len(window_pkts) else 0
        stage = ""
        if label:
            stage = max(
                [p.stage for p in window_pkts if p.label == 1 and p.stage],
                default="",
            )

        return NetworkState(
            timestamp=win_start.isoformat().replace("+00:00", "Z"),
            features=feats,
            src_ip=src,
            dst_ip=dst,
            label=label,
            stage=stage or None,
        )


def compute_window_features(pkts: List[PacketRecord], actual_window_seconds: float = None) -> Dict[str, float]:
    """
    Legacy function for backward compatibility.
    Computes base features only.
    """
    return compute_base_features(pkts, actual_window_seconds=actual_window_seconds)
