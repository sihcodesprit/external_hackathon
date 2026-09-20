"""
Entropy features — Shannon entropy and temporal entropy trajectories.

Implements H(X) = -Σ p(x) log2 p(x) for multiple distributions.
Also computes temporal derivatives: ΔH(t), Δ²H(t).
"""

import math
from collections import Counter
from typing import Dict, List, Optional


def shannon_entropy(values: List) -> float:
    """Compute Shannon entropy of a list of values."""
    if not values:
        return 0.0
    counts = Counter(values)
    total = float(len(values))
    entropy = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def compute_entropy_features(records: List[Dict],
                              prev_entropy: Optional[Dict[str, float]] = None,
                              prev2_entropy: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """
    Compute entropy features for a window of packet/flow records.

    Args:
        records: List of packet/flow dicts with fields like src_port, dst_port,
                 protocol, src_ip, dst_ip, payload_size, packet_size, tcp_flags
        prev_entropy: Previous window's entropy values (for delta)
        prev2_entropy: Two windows ago entropy values (for acceleration)

    Returns:
        Dict of entropy features including temporal derivatives
    """
    if not records:
        return _empty_entropy_features()

    # Extract value lists
    src_ports = [r.get("src_port", 0) for r in records if r.get("src_port")]
    dst_ports = [r.get("dst_port", 0) for r in records if r.get("dst_port")]
    protocols = [r.get("protocol", "") for r in records if r.get("protocol")]
    src_ips = [r.get("src_ip", "") for r in records if r.get("src_ip")]
    dst_ips = [r.get("dst_ip", "") for r in records if r.get("dst_ip")]
    payload_sizes = [r.get("payload_size", 0) for r in records]
    packet_sizes = [r.get("bytes_sent", 0) for r in records]
    tcp_flags = [r.get("flags", "") for r in records if r.get("flags")]

    # Base entropies
    entropies = {
        "src_port_entropy": shannon_entropy(src_ports),
        "dst_port_entropy": shannon_entropy(dst_ports),
        "protocol_entropy": shannon_entropy(protocols),
        "src_ip_entropy": shannon_entropy(src_ips),
        "dst_ip_entropy": shannon_entropy(dst_ips),
        "payload_size_entropy": shannon_entropy(payload_sizes),
        "packet_size_entropy": shannon_entropy(packet_sizes),
        "tcp_flag_entropy": shannon_entropy(tcp_flags),
    }

    # Temporal derivatives
    if prev_entropy:
        base_keys = list(entropies.keys())
        for key in base_keys:
            val = entropies[key]
            prev_val = prev_entropy.get(key, 0.0)
            entropies[f"{key}_delta"] = val - prev_val

            if prev2_entropy:
                prev2_val = prev2_entropy.get(key, 0.0)
                # Acceleration = Δ(current) - Δ(previous) = (val - prev) - (prev - prev2)
                entropies[f"{key}_acceleration"] = (val - prev_val) - (prev_val - prev2_val)
            else:
                entropies[f"{key}_acceleration"] = 0.0
    else:
        base_keys = list(entropies.keys())
        for key in base_keys:
            entropies[f"{key}_delta"] = 0.0
            entropies[f"{key}_acceleration"] = 0.0

    return entropies


def _empty_entropy_features() -> Dict[str, float]:
    """Return zero-filled entropy features."""
    base_keys = [
        "src_port_entropy", "dst_port_entropy", "protocol_entropy",
        "src_ip_entropy", "dst_ip_entropy", "payload_size_entropy",
        "packet_size_entropy", "tcp_flag_entropy",
    ]
    result = {}
    for key in base_keys:
        result[key] = 0.0
        result[f"{key}_delta"] = 0.0
        result[f"{key}_acceleration"] = 0.0
    return result


def update_entropy_history(entropy_history: List[Dict],
                           current: Dict,
                           max_history: int = 3) -> List[Dict]:
    """Maintain a rolling history of entropy features for temporal derivatives."""
    history = entropy_history + [current]
    if len(history) > max_history:
        history = history[-max_history:]
    return history
