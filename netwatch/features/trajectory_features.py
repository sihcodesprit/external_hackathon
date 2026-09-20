"""
Trajectory Features — Temporal derivatives of key state variables.

Computes value(t), delta(t), acceleration(t) for important features
to capture direction and speed of change.
"""

from collections import deque
from typing import Dict, List, Optional, Set, Tuple


class TrajectoryTracker:
    """Tracks temporal trajectory of key features across windows."""

    def __init__(self, max_history: int = 5,
                 tracked_features: Optional[Set[str]] = None):
        self.max_history = max_history
        self.tracked_features = tracked_features or {
            "syn_rate",
            "port_entropy",
            "graph_density",
            "packet_rate",
            "connection_rate",
            "unique_dst_ports",
            "half_open_ratio",
            "rst_rate",
            "ack_rate",
            "payload_mean",
        }
        self.history: deque = deque(maxlen=max_history)

    def update(self, features: Dict[str, float]) -> Dict[str, float]:
        """Add current features and compute trajectory features."""
        # Filter to tracked features
        current = {k: features.get(k, 0.0) for k in self.tracked_features}
        self.history.append(current)

        trajectory = {}

        if len(self.history) >= 2:
            # Delta = current - previous
            prev = self.history[-2]
            for key in self.tracked_features:
                trajectory[f"{key}_delta"] = current[key] - prev.get(key, 0.0)
        else:
            for key in self.tracked_features:
                trajectory[f"{key}_delta"] = 0.0

        if len(self.history) >= 3:
            # Acceleration = Δ(current) - Δ(previous)
            # = (current - prev) - (prev - prev2)
            prev = self.history[-2]
            prev2 = self.history[-3]
            for key in self.tracked_features:
                delta_curr = current[key] - prev.get(key, 0.0)
                delta_prev = prev.get(key, 0.0) - prev2.get(key, 0.0)
                trajectory[f"{key}_acceleration"] = delta_curr - delta_prev
        else:
            for key in self.tracked_features:
                trajectory[f"{key}_acceleration"] = 0.0

        return trajectory

    def get_history(self) -> List[Dict[str, float]]:
        return list(self.history)


def compute_trajectory_features(features: Dict[str, float],
                                 tracker: Optional[TrajectoryTracker] = None) -> Tuple[Dict[str, float], TrajectoryTracker]:
    """Compute trajectory features, creating tracker if needed."""
    if tracker is None:
        tracker = TrajectoryTracker()

    trajectory = tracker.update(features)
    return trajectory, tracker
