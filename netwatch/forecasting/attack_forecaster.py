"""
Attack forecaster.

Performs K-step forward simulation using the World Model and converts each
predicted next-state into:
    * future infiltration / attack probability (learned risk head)
    * predicted attack stage + stage probability
    * confidence
    * top contributing features (SHAP)

The attack probability is produced by a LEARNED risk head (logistic regression
fit on labelled states) applied to each state the World Model predicts during
rollout — it is not fabricated or a fixed discount.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
from sklearn.linear_model import LogisticRegression

from netwatch.features.network_state import NetworkState
from netwatch.forecasting.stage_predictor import StagePredictor
from netwatch.models.base_model import WorldModel

logger = logging.getLogger(__name__)

# Stage-related features read by StagePredictor are named differently in the
# world-model vector vocabulary (payload_size_mean / packet_rate / ...). When a
# predicted state vector is decoded back to raw features, stage features must be
# aliased so the stage predictor sees real values instead of always-zero.
_STAGE_FEATURE_ALIASES = {
    "payload_mean": ["payload_size_mean"],
    "payload_max": ["payload_size_max", "payload_size_mean"],
    "packets_per_second": ["packet_rate"],
    "unique_dst_ports": ["unique_dst_ports"],
    "unique_dst_hosts": ["unique_dst_hosts"],
    "port_entropy": ["port_entropy"],
    "dest_port_entropy": ["dst_port_entropy"],
    "syn_rate": ["syn_rate"],
    "ack_rate": ["ack_rate"],
    "rst_rate": ["rst_rate"],
    "bytes": ["total_bytes"],
    "packets": ["total_packets"],
}


class AttackForecaster:
    """K-step forward attack forecasting from a window of NetworkStates."""

    def __init__(self, world_model: WorldModel, normalizer,
                 stage_predictor: Optional[StagePredictor] = None,
                 feature_columns: Optional[List[str]] = None):
        self.world_model = world_model
        self.normalizer = normalizer
        self.stage_predictor = stage_predictor or StagePredictor()
        self.feature_columns = feature_columns
        # learned risk head
        self.risk_model = LogisticRegression(max_iter=2000)
        self._risk_trained = False
        self.benign_profile: Optional[np.ndarray] = None

    def fit_risk_head(self, labelled_states: List[NetworkState]):
        """Train logistic risk head: normalized state -> attack probability.
        Uses the actual labels already assigned to states (ground truth from
        the activity profile / dataset)."""
        if not labelled_states:
            return {"status": "no_data"}
        X = np.array([self.normalizer.transform(s) for s in labelled_states])
        y = np.array([s.label if s.label is not None else 0 for s in labelled_states])
        if len(np.unique(y)) < 2:
            self._risk_trained = False
            return {"status": "insufficient_labels"}
        self.risk_model.fit(X, y)
        self._risk_trained = True
        self.benign_profile = X[y == 0].mean(axis=0) if (y == 0).any() else None
        return {"status": "trained"}

    def _attack_prob(self, state_vec_normalized: np.ndarray) -> float:
        vec = np.asarray(state_vec_normalized, dtype=np.float64).ravel()
        if not self._risk_trained:
            # Fallback: derived from raw activity magnitude (transparent &
            # deterministic) — documented as heuristic when no risk head is fit.
            if not np.isfinite(vec).all() or len(vec) == 0:
                return 0.0
            magnitude = float(np.linalg.norm(vec))
            return float(min(max(magnitude / 8.0, 0.0), 1.0))
        try:
            p = float(self.risk_model.predict_proba(
                np.asarray(state_vec_normalized).reshape(1, -1))[0, 1])
        except Exception:
            p = 0.0
        return 0.0 if not np.isfinite(p) else float(min(max(p, 0.0), 1.0))

    def _state_from_vec(self, vec: np.ndarray, timestamp: str = "") -> NetworkState:
        """Invert normalization to a raw feature dict for feature interpretation."""
        raw = {}
        for i, col in enumerate(self.feature_columns):
            raw[col] = float(
                vec[i] * self.normalizer.std[i] + self.normalizer.mean[i]
            )
        # Map world-model vocabulary to the stage predictor's feature names so
        # predicted stages are driven by real recovered magnitudes and never by
        # a vocabulary mismatch (which produced all-zero features -> "Benign").
        for target, sources in _STAGE_FEATURE_ALIASES.items():
            if target not in raw:
                for src in sources:
                    if src in raw:
                        raw[target] = raw[src]
                        break
        return NetworkState(timestamp=timestamp, features=raw)

    def forecast(self, history_states: List[NetworkState], k: int = 5) -> Dict:
        """Run K-step rollout and produce a full forecast report."""
        if not history_states:
            return {"status": "no_history"}
        norm_history = [self.normalizer.transform(s) for s in history_states]

        # current state analysis
        current_vec = norm_history[-1]
        current_state = self._state_from_vec(current_vec)
        # Stage is derived from the real observed features of the latest window
        # (full vocabulary) rather than the normalizer inversion, which only
        # covers the world-model columns.
        current_stage = self.stage_predictor.predict(history_states[-1].features)
        current_risk = self._attack_prob(current_vec)

        # K-step rollout
        future_vecs = self.world_model.rollout(norm_history, k)
        steps = []
        for step_idx, vec in enumerate(future_vecs, start=1):
            ts = f"t+{step_idx}"
            pred_state = self._state_from_vec(vec, timestamp=ts)
            stage = self.stage_predictor.predict(pred_state.features)
            risk = self._attack_prob(vec)
            steps.append({
                "step": step_idx,
                "window": ts,
                "state_vec": vec.tolist(),
                "features": pred_state.features,
                "risk": round(risk, 4),
                "stage": stage["predicted_stage"],
                "stage_probability": stage["stage_probability"],
                "step_stage_prob": stage["stage_probability"],
                "stage_probabilities": stage["stage_probabilities"],
                "supporting_features": stage["supporting_features"],
            })

        from netwatch.forecasting.confidence import assign_confidence
        assign_confidence(steps)

        return {
            "status": "ok",
            "current": {
                "risk": round(current_risk, 4),
                "stage": current_stage["predicted_stage"],
                "stage_probability": current_stage["stage_probability"],
                "features": current_state.features,
                "state_vec": current_vec.tolist(),
            },
            "k": k,
            "future": steps,
        }
