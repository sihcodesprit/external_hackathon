"""
Baseline Deviation Features — Z-scores, percentiles, and deviations from benign baseline.

Builds a benign baseline from normal traffic and computes how much
current features deviate from that baseline.
"""

from collections import deque
from typing import Dict, List, Optional, Set, Tuple

import numpy as np


class BaselineTracker:
    """Maintains benign baseline statistics for feature deviation computation."""
    
    def __init__(self, max_history: int = 1000,
                 tracked_features: Optional[Set[str]] = None,
                 min_samples: int = 30):
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
            "syn_ack_ratio",
            "dst_entropy",
        }
        self.min_samples = min_samples
        self.benign_history: Dict[str, deque] = {
            f: deque(maxlen=max_history) for f in self.tracked_features
        }
        self._baseline_stats: Dict[str, Dict] = {}
        self._initialized = False
    
    def update(self, features: Dict[str, float], is_benign: bool = True) -> Dict[str, float]:
        """Update baseline with new observation (if benign) and compute deviations."""
        if is_benign:
            for key in self.tracked_features:
                if key in features:
                    self.benign_history[key].append(features[key])
        
        # Recompute baseline stats periodically
        if len(self.benign_history[next(iter(self.tracked_features))]) >= self.min_samples:
            self._recompute_baseline()
            self._initialized = True
        
        # Compute deviations
        deviations = {}
        if self._initialized:
            for key in self.tracked_features:
                val = features.get(key, 0.0)
                stats = self._baseline_stats.get(key, {})
                
                # Z-score
                mean = stats.get("mean", 0.0)
                std = stats.get("std", 1.0)
                deviations[f"{key}_zscore"] = (val - mean) / max(std, 1e-6)
                
                # Percentile (approximate)
                history = list(self.benign_history[key])
                if history:
                    percentile = np.searchsorted(np.sort(history), val) / len(history)
                    deviations[f"{key}_percentile"] = float(percentile)
                else:
                    deviations[f"{key}_percentile"] = 0.5
                
                # Absolute deviation
                deviations[f"{key}_deviation"] = val - mean
        else:
            # Not enough baseline data yet
            for key in self.tracked_features:
                deviations[f"{key}_zscore"] = 0.0
                deviations[f"{key}_percentile"] = 0.5
                deviations[f"{key}_deviation"] = 0.0
        
        return deviations
    
    def _recompute_baseline(self):
        """Recompute mean, std, percentiles for each tracked feature."""
        for key in self.tracked_features:
            history = list(self.benign_history[key])
            if len(history) >= self.min_samples:
                arr = np.array(history)
                self._baseline_stats[key] = {
                    "mean": float(np.mean(arr)),
                    "std": float(np.std(arr)),
                    "min": float(np.min(arr)),
                    "max": float(np.max(arr)),
                    "q25": float(np.percentile(arr, 25)),
                    "q50": float(np.percentile(arr, 50)),
                    "q75": float(np.percentile(arr, 75)),
                }
    
    def get_baseline_stats(self) -> Dict:
        return self._baseline_stats.copy()
    
    def is_initialized(self) -> bool:
        return self._initialized


def compute_baseline_features(features: Dict[str, float],
                               tracker: Optional[BaselineTracker] = None,
                               is_benign: bool = True) -> Tuple[Dict[str, float], BaselineTracker]:
    """Compute baseline deviation features."""
    if tracker is None:
        tracker = BaselineTracker()
    
    deviations = tracker.update(features, is_benign=is_benign)
    return deviations, tracker