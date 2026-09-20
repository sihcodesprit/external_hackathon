"""
Feature Registry — Centralized feature configuration.

Defines all available feature groups and their constituent features.
This avoids hard-coding feature counts and allows dynamic feature selection
via configuration (config.yaml).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FeatureGroup:
    """A logical group of related features."""
    name: str
    description: str
    features: List[str]
    enabled: bool = True
    required: bool = False  # if True, cannot be disabled


@dataclass
class FeatureRegistry:
    """Central registry of all feature groups and individual features."""

    groups: Dict[str, FeatureGroup] = field(default_factory=dict)

    def register_group(self, group: FeatureGroup):
        self.groups[group.name] = group

    def get_enabled_features(self) -> List[str]:
        """Return flat list of all enabled feature names in canonical order."""
        features = []
        for group_name in self.get_canonical_group_order():
            group = self.groups.get(group_name)
            if group and group.enabled:
                features.extend(group.features)
        return features

    def get_canonical_group_order(self) -> List[str]:
        """Canonical order for feature vector construction."""
        return [
            "traffic",
            "packet",
            "flow",
            "tcp_handshake",
            "entropy",
            "temporal",
            "graph",
            "markov",
            "trajectory",
            "baseline_deviation",
        ]

    def get_features_by_group(self, group_name: str) -> List[str]:
        group = self.groups.get(group_name)
        return group.features if group else []

    def is_enabled(self, group_name: str) -> bool:
        group = self.groups.get(group_name)
        return group.enabled if group else False

    def enable_group(self, group_name: str, enabled: bool = True):
        if group_name in self.groups and not self.groups[group_name].required:
            self.groups[group_name].enabled = enabled

    def get_feature_metadata(self) -> Dict:
        """Return metadata for all features."""
        return {
            group_name: {
                "description": group.description,
                "features": group.features,
                "enabled": group.enabled,
                "required": group.required,
            }
            for group_name, group in self.groups.items()
        }


# ── Global registry instance ──────────────────────────────────

REGISTRY = FeatureRegistry()

# Register all feature groups in canonical order

REGISTRY.register_group(FeatureGroup(
    name="traffic",
    description="Aggregate traffic volume and rate features",
    features=[
        "total_packets",
        "total_bytes",
        "packet_rate",
        "byte_rate",
        "flow_rate",
        "connection_rate",
        "average_packet_size",
        "packet_size_variance",
        "flow_duration_mean",
    ],
    required=True,
))

REGISTRY.register_group(FeatureGroup(
    name="packet",
    description="Per-packet header and payload characteristics",
    features=[
        "ttl_mean",
        "ttl_variance",
        "tcp_window_mean",
        "tcp_window_variance",
        "ip_fragmentation_count",
        "payload_size_mean",
        "payload_size_variance",
        "packet_size_mean",
        "packet_size_variance",
        "iat_mean",
        "iat_variance",
        "iat_max",
        "tcp_retransmissions",
        "protocol_tcp",
        "protocol_udp",
        "protocol_icmp",
        "src_port",
        "dst_port",
    ],
    required=True,
))

REGISTRY.register_group(FeatureGroup(
    name="flow",
    description="Bidirectional flow-level features",
    features=[
        "src_ip",
        "dst_ip",
        "src_port",
        "dst_port",
        "protocol",
        "tcp_flags",
        "bytes",
        "packets",
        "duration",
        "iat_mean",
        "iat_variance",
        "iat_max",
        "fwd_packets",
        "bwd_packets",
        "fwd_bytes",
        "bwd_bytes",
        "bidirectional_packet_ratio",
        "bidirectional_byte_ratio",
    ],
    required=False,
))

REGISTRY.register_group(FeatureGroup(
    name="tcp_handshake",
    description="TCP handshake asymmetry and ghost ratio features",
    features=[
        "syn_count",
        "syn_ack_count",
        "ack_count",
        "rst_count",
        "fin_count",
        "syn_ack_ratio",
        "syn_synack_ratio",
        "rst_syn_ratio",
        "half_open_ratio",
        "ack_completion_ratio",
        "delta_syn_rate",
        "delta_syn_ack_ratio",
        "delta_half_open_ratio",
        "delta_rst_rate",
    ],
    required=False,
))

REGISTRY.register_group(FeatureGroup(
    name="entropy",
    description="Shannon entropy features for randomness detection",
    features=[
        "src_port_entropy",
        "dst_port_entropy",
        "protocol_entropy",
        "dst_ip_entropy",
        "src_ip_entropy",
        "payload_size_entropy",
        "packet_size_entropy",
        "tcp_flag_entropy",
        # Temporal entropy trajectories
        "port_entropy_delta",
        "port_entropy_acceleration",
        "dst_entropy_delta",
        "dst_entropy_acceleration",
        "payload_entropy_delta",
        "payload_entropy_acceleration",
    ],
    required=False,
))

REGISTRY.register_group(FeatureGroup(
    name="temporal",
    description="Inter-arrival time, jitter, periodicity, burstiness",
    features=[
        "iat_mean",
        "iat_std",
        "iat_variance",
        "iat_cv",  # coefficient of variation
        "iat_min",
        "iat_max",
        "iat_autocorr",
        "periodicity_score",
        "burstiness",
        "fft_dominant_freq",
        "fft_spectral_power",
    ],
    required=False,
))

REGISTRY.register_group(FeatureGroup(
    name="graph",
    description="Dynamic network graph topology features",
    features=[
        "node_count",
        "edge_count",
        "graph_density",
        "average_degree",
        "degree_variance",
        "clustering_coefficient",
        "new_edges",
        "removed_edges",
        "new_destinations",
        "new_sources",
        "eigenvector_centrality_max",
        "betweenness_centrality_max",
        "pagerank_max",
        "density_delta",
        "degree_delta",
        "centrality_delta",
        "new_edges_rate",
        "new_destinations_rate",
    ],
    required=False,
))

REGISTRY.register_group(FeatureGroup(
    name="markov",
    description="Protocol/TCP state transition probabilities",
    features=[
        "p_synack_given_syn",
        "p_rst_given_syn",
        "p_ack_given_synack",
        "p_fin_given_ack",
        "p_rst_given_ack",
        "p_timeout_given_syn",
    ],
    required=False,
))

REGISTRY.register_group(FeatureGroup(
    name="trajectory",
    description="Temporal derivatives (delta, acceleration) of key state variables",
    features=[
        "syn_rate_delta",
        "syn_rate_acceleration",
        "port_entropy_delta",
        "port_entropy_acceleration",
        "graph_density_delta",
        "graph_density_acceleration",
        "packet_rate_delta",
        "packet_rate_acceleration",
        "connection_rate_delta",
        "connection_rate_acceleration",
        "unique_dst_ports_delta",
        "unique_dst_ports_acceleration",
    ],
    required=False,
))

REGISTRY.register_group(FeatureGroup(
    name="baseline_deviation",
    description="Deviation from benign baseline (z-score, percentile)",
    features=[
        "syn_rate_zscore",
        "port_entropy_zscore",
        "packet_rate_zscore",
        "graph_density_zscore",
        "syn_rate_percentile",
        "port_entropy_percentile",
        "packet_rate_percentile",
        "graph_density_percentile",
        "syn_rate_deviation",
        "port_entropy_deviation",
        "packet_rate_deviation",
        "graph_density_deviation",
    ],
    required=False,
))


def build_registry_from_config(config: Dict) -> FeatureRegistry:
    """Build a feature registry from a configuration dict."""
    registry = FeatureRegistry()

    # Copy base groups
    for group_name in REGISTRY.get_canonical_group_order():
        base_group = REGISTRY.groups.get(group_name)
        if base_group:
            enabled = config.get("features", {}).get(group_name, base_group.enabled)
            # Required groups cannot be disabled
            if base_group.required:
                enabled = True
            registry.register_group(FeatureGroup(
                name=base_group.name,
                description=base_group.description,
                features=base_group.features.copy(),
                enabled=enabled,
                required=base_group.required,
            ))
    return registry


def get_feature_columns(registry: Optional[FeatureRegistry] = None) -> List[str]:
    """Get the flat list of enabled feature columns."""
    reg = registry or REGISTRY
    return reg.get_enabled_features()


def get_n_features(registry: Optional[FeatureRegistry] = None) -> int:
    """Get the number of enabled features."""
    return len(get_feature_columns(registry))
