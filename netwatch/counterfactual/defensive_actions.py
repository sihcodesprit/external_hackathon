"""
Defensive actions for counterfactual simulation.

Each action is a *simulation-only* mutation applied to a NetworkState feature
vector (in normalized space) that represents the defender's intervention.
NO actual network blocking is ever performed — this is decision support.

Each action provides:
    id, label, description, and apply(state_vec, features) -> modified vector

Actions use dynamic feature column lookup instead of hardcoded indices.
"""

from typing import Callable, Dict, List

import numpy as np


class DefensiveAction:
    def __init__(self, action_id: str, label: str, description: str,
                 apply_fn: Callable[[np.ndarray, Dict[str, float]], np.ndarray]):
        self.id = action_id
        self.label = label
        self.description = description
        self.apply_fn = apply_fn

    def apply(self, state_vec: np.ndarray, features: Dict[str, float]) -> np.ndarray:
        return self.apply_fn(np.asarray(state_vec, dtype=np.float64).copy(), features)


def _get_idx_map(feature_columns: List[str]) -> Dict[str, int]:
    """Build a name->index map from the feature column list."""
    return {name: i for i, name in enumerate(feature_columns)}


def _no_action(vec, feats, idx=None):
    return vec


def _block_source(vec, feats, idx=None):
    """Simulate: source no longer reaches host -> drop traffic features to benign baseline."""
    nv = vec.copy()
    idx = idx or {}
    for key in ["packets_per_second", "connection_rate", "unique_dst_ports",
                "unique_dst_hosts", "syn_rate", "ack_rate", "rst_rate",
                "syn_ack_ratio", "port_entropy", "packets", "bytes"]:
        if key in idx:
            nv[idx[key]] = 0.0
    return nv


def _block_dest_port(vec, feats, idx=None):
    """Simulate: targeted port blocked -> partial traffic reduction."""
    nv = vec.copy()
    idx = idx or {}
    for key in ["packets_per_second", "connection_rate", "unique_dst_ports",
                "unique_dst_hosts", "syn_rate", "rst_rate", "port_entropy", "packets"]:
        if key in idx:
            nv[idx[key]] = nv[idx[key]] * 0.25
    if "bytes" in idx:
        nv[idx["bytes"]] = nv[idx["bytes"]] * 0.5
    if "payload_mean" in idx:
        nv[idx["payload_mean"]] = nv[idx["payload_mean"]] * 0.7
    return nv


def _isolate_host(vec, feats, idx=None):
    """Simulate: isolate the host -> cut all inbound connections."""
    return _block_source(vec, feats, idx)


def _terminate_flow(vec, feats, idx=None):
    """Simulate: terminate the active suspicious flow."""
    nv = vec.copy()
    idx = idx or {}
    if "packets_per_second" in idx:
        nv[idx["packets_per_second"]] = 0.0
    if "connection_rate" in idx:
        nv[idx["connection_rate"]] = 0.0
    if "syn_rate" in idx:
        nv[idx["syn_rate"]] = 0.0
    if "packets" in idx:
        nv[idx["packets"]] = nv[idx["packets"]] * 0.2
    return nv


def _restrict_path(vec, feats, idx=None):
    """Simulate: restrict communication path."""
    nv = vec.copy()
    idx = idx or {}
    if "unique_dst_hosts" in idx:
        nv[idx["unique_dst_hosts"]] = nv[idx["unique_dst_hosts"]] * 0.1
    if "unique_dst_ports" in idx:
        nv[idx["unique_dst_ports"]] = nv[idx["unique_dst_ports"]] * 0.2
    if "packets_per_second" in idx:
        nv[idx["packets_per_second"]] = nv[idx["packets_per_second"]] * 0.3
    return nv


# Build ACTIONS dynamically — will be initialized with feature columns at runtime
_ACTIONS_REGISTRY: Dict[str, DefensiveAction] = {}


def _build_actions(feature_columns: List[str]) -> Dict[str, DefensiveAction]:
    """Build the actions dictionary using dynamic feature columns."""
    idx = _get_idx_map(feature_columns)
    return {
        "no_action": DefensiveAction(
            "no_action", "No Action",
            "Do nothing — observe the natural attack evolution.",
            lambda vec, feats: _no_action(vec, feats, idx),
        ),
        "block_source": DefensiveAction(
            "block_source", "Block Source",
            "Block the attacker source IP at the perimeter.",
            lambda vec, feats: _block_source(vec, feats, idx),
        ),
        "block_dest_port": DefensiveAction(
            "block_dest_port", "Block Destination Port",
            "Block the targeted destination port.",
            lambda vec, feats: _block_dest_port(vec, feats, idx),
        ),
        "isolate_host": DefensiveAction(
            "isolate_host", "Isolate Host",
            "Isolate the affected host from the network.",
            lambda vec, feats: _isolate_host(vec, feats, idx),
        ),
        "terminate_flow": DefensiveAction(
            "terminate_flow", "Terminate Flow",
            "Terminate the active suspicious communication flow.",
            lambda vec, feats: _terminate_flow(vec, feats, idx),
        ),
        "restrict_path": DefensiveAction(
            "restrict_path", "Restrict Path",
            "Restrict the communication path to/from the host.",
            lambda vec, feats: _restrict_path(vec, feats, idx),
        ),
    }


# Default actions with fallback (uses basic feature names if columns not available)
_DEFAULT_COLUMNS = [
    "bytes", "packets", "ttl_mean", "payload_mean", "payload_max",
    "tcp_window_mean", "packets_per_second", "connection_rate",
    "unique_dst_ports", "unique_dst_hosts", "syn_rate", "ack_rate",
    "rst_rate", "syn_ack_ratio", "port_entropy",
]

ACTIONS: Dict[str, DefensiveAction] = _build_actions(_DEFAULT_COLUMNS)


def get_actions_for_columns(feature_columns: List[str]) -> Dict[str, DefensiveAction]:
    """Get actions built with the correct feature column mapping."""
    return _build_actions(feature_columns)


def get_action(action_id: str) -> DefensiveAction:
    return ACTIONS[action_id]


def available_actions() -> List[str]:
    return list(ACTIONS.keys())
