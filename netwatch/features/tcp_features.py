"""
TCP Handshake / Ghost Ratio Features.

Implements asymmetric handshake analysis for detecting:
- Reconnaissance (SYN scans)
- SYN flooding
- Incomplete handshakes
- Suspicious asymmetric behavior
"""

from typing import Dict, List, Optional


def compute_tcp_handshake_features(records: List[Dict],
                                    prev_features: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """
    Compute TCP handshake asymmetry features from a window of records.

    Args:
        records: List of packet/flow dicts with 'flags' field (TCP flags string)
        prev_features: Previous window's handshake features (for delta)

    Returns:
        Dict of handshake features including temporal derivatives
    """
    if not records:
        return _empty_handshake_features()

    # Count TCP flags
    syn_count = 0
    syn_ack_count = 0
    ack_count = 0
    rst_count = 0
    fin_count = 0

    for r in records:
        flags = r.get("flags", "").upper()
        if "S" in flags and "A" not in flags:
            syn_count += 1
        elif "S" in flags and "A" in flags:
            syn_ack_count += 1
        elif "A" in flags and "S" not in flags:
            ack_count += 1
        if "R" in flags:
            rst_count += 1
        if "F" in flags:
            fin_count += 1

    # Derived ratios
    syn_ack_ratio = syn_count / max(ack_count, 1) if ack_count > 0 else float(syn_count)
    syn_synack_ratio = syn_count / max(syn_ack_count, 1) if syn_ack_count > 0 else float(syn_count)
    rst_syn_ratio = rst_count / max(syn_count, 1) if syn_count > 0 else 0.0
    half_open_ratio = syn_count / max(syn_ack_count + ack_count, 1)
    ack_completion_ratio = ack_count / max(syn_ack_count, 1) if syn_ack_count > 0 else 0.0

    # Rates (per window - window duration handled by caller)
    syn_rate = float(syn_count)
    syn_ack_rate = float(syn_ack_count)
    rst_rate = float(rst_count)

    features = {
        "syn_count": float(syn_count),
        "syn_ack_count": float(syn_ack_count),
        "ack_count": float(ack_count),
        "rst_count": float(rst_count),
        "fin_count": float(fin_count),
        "syn_ack_ratio": syn_ack_ratio,
        "syn_synack_ratio": syn_synack_ratio,
        "rst_syn_ratio": rst_syn_ratio,
        "half_open_ratio": half_open_ratio,
        "ack_completion_ratio": ack_completion_ratio,
        "syn_rate": syn_rate,
        "syn_ack_rate": syn_ack_rate,
        "rst_rate": rst_rate,
    }

    # Temporal derivatives
    if prev_features:
        features["delta_syn_rate"] = syn_rate - prev_features.get("syn_rate", 0.0)
        features["delta_syn_ack_ratio"] = syn_ack_ratio - prev_features.get("syn_ack_ratio", 0.0)
        features["delta_half_open_ratio"] = half_open_ratio - prev_features.get("half_open_ratio", 0.0)
        features["delta_rst_rate"] = rst_rate - prev_features.get("rst_rate", 0.0)
    else:
        features["delta_syn_rate"] = 0.0
        features["delta_syn_ack_ratio"] = 0.0
        features["delta_half_open_ratio"] = 0.0
        features["delta_rst_rate"] = 0.0

    return features


def _empty_handshake_features() -> Dict[str, float]:
    keys = [
        "syn_count", "syn_ack_count", "ack_count", "rst_count", "fin_count",
        "syn_ack_ratio", "syn_synack_ratio", "rst_syn_ratio",
        "half_open_ratio", "ack_completion_ratio",
        "syn_rate", "syn_ack_rate", "rst_rate",
        "delta_syn_rate", "delta_syn_ack_ratio",
        "delta_half_open_ratio", "delta_rst_rate",
    ]
    return {k: 0.0 for k in keys}


def update_handshake_history(history: List[Dict],
                             current: Dict,
                             max_history: int = 3) -> List[Dict]:
    """Maintain rolling history of handshake features."""
    history = history + [current]
    if len(history) > max_history:
        history = history[-max_history:]
    return history
