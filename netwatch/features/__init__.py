"""
Feature engineering package for the Counterfactual Cyber World Model.

Modules:
- network_state: NetworkState dataclass and StateBuilder
- feature_registry: Centralized feature configuration
- packet_features: Packet-level feature extraction
- flow_features: Flow-level feature extraction
- tcp_features: TCP handshake / ghost ratio features
- entropy_features: Shannon entropy and temporal trajectories
- temporal_features: IAT, jitter, periodicity, burstiness, FFT
- graph_features: Dynamic network graph topology
- trajectory_features: Temporal derivatives (delta, acceleration)
- baseline_features: Benign baseline deviation (z-score, percentile)
- sequences: Temporal sequence dataset construction
"""

from netwatch.features.network_state import NetworkState, StateBuilder, compute_window_features
from netwatch.features.feature_registry import REGISTRY, get_feature_columns, get_n_features
from netwatch.features.sequences import (
    StateNormalizer,
    assign_labels_and_stages,
    build_sequences,
    build_seq_labels,
    temporal_split,
    split_by_group,
)

__all__ = [
    "NetworkState",
    "StateBuilder",
    "compute_window_features",
    "REGISTRY",
    "get_feature_columns",
    "get_n_features",
    "StateNormalizer",
    "assign_labels_and_stages",
    "build_sequences",
    "build_seq_labels",
    "temporal_split",
    "split_by_group",
]