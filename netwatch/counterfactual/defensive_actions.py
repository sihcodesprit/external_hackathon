"""
Defensive actions for counterfactual simulation.

Each action is a *simulation-only* mutation applied to a NetworkState feature
vector (in normalized space) that represents the defender's intervention.
NO actual network blocking is ever performed — this is decision support.

Each action provides:
    id, label, description, and apply(state_vec, features) -> modified vector
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
        return self.apply_fn(np.asarray(state_vec, dtype=np.float64).copy(),
                             features)


def _no_action(vec, feats):
    return vec


def _block_source(vec, feats):
    # Simulate: source no longer reaches host -> drop connection rate, SYN/RST,
    # and port activity down to benign baseline (normalized ~0).
    nv = vec.copy()
    # indices by feature name (assumed FEATURE_COLUMNS ordering)
    idx = {name: i for i, name in enumerate(
        ["bytes", "packets", "ttl_mean", "payload_mean", "payload_max",
         "tcp_window_mean", "packets_per_second", "connection_rate",
         "unique_dst_ports", "unique_dst_hosts", "syn_rate", "ack_rate",
         "rst_rate", "syn_ack_ratio", "port_entropy"])}
    for key in ["packets_per_second", "connection_rate", "unique_dst_ports",
                "unique_dst_hosts", "syn_rate", "ack_rate", "rst_rate",
                "syn_ack_ratio", "port_entropy", "packets", "bytes"]:
        if key in idx:
            nv[idx[key]] = 0.0
    return nv


def _block_dest_port(vec, feats):
    # Simulate: targeted port blocked -> reduce traffic magnitude to benign
    nv = vec.copy()
    idx = {name: i for i, name in enumerate(
        ["bytes", "packets", "ttl_mean", "payload_mean", "payload_max",
         "tcp_window_mean", "packets_per_second", "connection_rate",
         "unique_dst_ports", "unique_dst_hosts", "syn_rate", "ack_rate",
         "rst_rate", "syn_ack_ratio", "port_entropy"])}
    for key in ["packets_per_second", "connection_rate", "unique_dst_ports",
                "unique_dst_hosts", "syn_rate", "rst_rate", "port_entropy",
                "packets"]:
        nv[idx[key]] = nv[idx[key]] * 0.25  # partial reduction
    nv[idx["bytes"]] = nv[idx["bytes"]] * 0.5
    nv[idx["payload_mean"]] = nv[idx["payload_mean"]] * 0.7
    return nv


def _isolate_host(vec, feats):
    # Simulate: isolate the host -> cut all inbound connections (~ block source
    # but also keep host's own normal traffic).
    return _block_source(vec, feats)


def _terminate_flow(vec, feats):
    # Simulate: terminate the active suspicious flow -> drop current session
    nv = vec.copy()
    idx = {name: i for i, name in enumerate(
        ["bytes", "packets", "ttl_mean", "payload_mean", "payload_max",
         "tcp_window_mean", "packets_per_second", "connection_rate",
         "unique_dst_ports", "unique_dst_hosts", "syn_rate", "ack_rate",
         "rst_rate", "syn_ack_ratio", "port_entropy"])}
    nv[idx["packets_per_second"]] = 0.0
    nv[idx["connection_rate"]] = 0.0
    nv[idx["syn_rate"]] = 0.0
    nv[idx["packets"]] = nv[idx["packets"]] * 0.2
    return nv


def _restrict_path(vec, feats):
    # Simulate: restrict communication path to/from the suspicious host
    nv = vec.copy()
    idx = {name: i for i, name in enumerate(
        ["bytes", "packets", "ttl_mean", "payload_mean", "payload_max",
         "tcp_window_mean", "packets_per_second", "connection_rate",
         "unique_dst_ports", "unique_dst_hosts", "syn_rate", "ack_rate",
         "rst_rate", "syn_ack_ratio", "port_entropy"])}
    nv[idx["unique_dst_hosts"]] = nv[idx["unique_dst_hosts"]] * 0.1
    nv[idx["unique_dst_ports"]] = nv[idx["unique_dst_ports"]] * 0.2
    nv[idx["packets_per_second"]] = nv[idx["packets_per_second"]] * 0.3
    return nv


ACTIONS: Dict[str, DefensiveAction] = {
    "no_action": DefensiveAction(
        "no_action", "No Action",
        "Do nothing — observe the natural attack evolution.",
        _no_action,
    ),
    "block_source": DefensiveAction(
        "block_source", "Block Source",
        "Block the attacker source IP at the perimeter.",
        _block_source,
    ),
    "block_dest_port": DefensiveAction(
        "block_dest_port", "Block Destination Port",
        "Block the targeted destination port.",
        _block_dest_port,
    ),
    "isolate_host": DefensiveAction(
        "isolate_host", "Isolate Host",
        "Isolate the affected host from the network.",
        _isolate_host,
    ),
    "terminate_flow": DefensiveAction(
        "terminate_flow", "Terminate Flow",
        "Terminate the active suspicious communication flow.",
        _terminate_flow,
    ),
    "restrict_path": DefensiveAction(
        "restrict_path", "Restrict Path",
        "Restrict the communication path to/from the host.",
        _restrict_path,
    ),
}


def get_action(action_id: str) -> DefensiveAction:
    return ACTIONS[action_id]


def available_actions() -> List[str]:
    return list(ACTIONS.keys())
