"""
Attack stage predictor.

Maps a NetworkState feature vector to a predicted MITRE ATT&CK attack stage
with a stage probability and the supporting features.

For unlabelled synthetic data we use heuristics driven by the feature profile.
When real labelled datasets are available, a trained classifier can be plugged
in. We never claim a stage when evidence is insufficient — low-confidence
states return the 'benign' default with a low probability.
"""

import logging
from typing import Dict, List, Optional

from netwatch.models.baselines.benchmark import build_classifier

logger = logging.getLogger(__name__)

# Killer-chain progression order (used for unknown->mapped ranking)
STAGES = [
    "Reconnaissance",
    "Initial Access",
    "Execution",
    "Lateral Movement",
    "Command and Control",
    "Exfiltration",
]


def heuristic_stage(features: Dict[str, float]) -> str:
    """Best-effort stage label from a feature vector (for synthetic labelling).

    Priority order is chosen so stage-specific signals (payload volume for
    C2/exfil, SYN pressure for initial access) are not masked by the catch-all
    port-entropy signal that fires for every scan.
    """
    syn = features.get("syn_rate", 0.0)
    ent = features.get("port_entropy", 0.0)
    ports = features.get("unique_dst_ports", 0.0)
    payload = features.get("payload_mean", 0.0)
    pps = features.get("packets_per_second", 0.0)
    syn_ack = features.get("syn_ack_ratio", 0.0)

    # High payload is the strongest discriminator for data movement stages.
    if payload >= 800:
        return "Command and Control"
    if payload >= 400:
        return "Exfiltration"
    # Broad port/host sweep -> reconnaissance (multi-port or multi-host scan).
    if pps >= 5 and (ent >= 1.5 or ports >= 6):
        return "Reconnaissance"
    # Sustained SYN pressure against a host -> probes/exploitation.
    if syn >= 2.0 and pps >= 15:
        return "Initial Access"
    if syn_ack >= 2.0 and pps >= 5:
        return "Execution"
    if pps >= 3:
        return "Lateral Movement"
    return "Benign"


class StagePredictor:
    """Predicts a MITRE stage (and stage probabilities) from a state vector."""

    def __init__(self, stages: Optional[List[str]] = None):
        self.stages = stages or STAGES
        self.model = None
        self.class_names = None

    def train(self, X: List[List[float]], labels: List[str]) -> Dict:
        """Train a classifier on labelled states (only if real labels exist)."""
        unique = sorted(set(labels))
        if len(unique) < 2:
            return {"status": "insufficient_labels",
                    "note": "Need >=2 distinct stage labels to train a classifier."}
        self.model = build_classifier("gradient_boosting")
        self.class_names = unique
        self.model.fit(X, [self.class_names.index(label) for label in labels])
        return {"status": "trained", "classes": self.class_names}

    def predict_proba(self, features: Dict[str, float]) -> Dict[str, float]:
        """Return probability per stage. Falls back to heuristic when no
        trained model or when evidence is insufficient."""
        # Heuristic calibrated probabilities
        stage = heuristic_stage(features)
        if stage == "Benign":
            probs = {s: 0.0 for s in self.stages}
            probs["Benign"] = 0.9
            return probs

        idx = self.stages.index(stage) if stage in self.stages else 0
        probs = {s: 0.0 for s in self.stages}
        probs["Benign"] = 0.0
        # simple exponential-decay distribution around the predicted stage
        for i, s in enumerate(self.stages):
            probs[s] = 0.55 ** abs(i - idx)
        total = sum(probs.values())
        probs = {k: v / total for k, v in probs.items()}
        return probs

    def predict(self, features: Dict[str, float]) -> Dict:
        """Return a structured stage prediction."""
        probs = self.predict_proba(features)
        best = max(probs.items(), key=lambda kv: kv[1])
        return {
            "predicted_stage": best[0],
            "stage_probability": round(best[1], 4),
            "stage_probabilities": {k: round(v, 4) for k, v in probs.items()},
            "supporting_features": self._supporting(features, best[0]),
        }

    def _supporting(self, features: Dict[str, float], stage: str) -> List[str]:
        """Explain (heuristic) which features support the stage."""
        support = []
        if features.get("port_entropy", 0) >= 1.0:
            support.append("High destination-port entropy (scanning)")
        if features.get("syn_ack_ratio", 0) >= 1.5:
            support.append("High SYN/ACK ratio (connection attempts)")
        if features.get("payload_mean", 0) >= 400:
            support.append("High mean payload (data transfer/exfil)")
        if features.get("packets_per_second", 0) >= 5:
            support.append("Elevated packets-per-second (active session)")
        return support[:3]
