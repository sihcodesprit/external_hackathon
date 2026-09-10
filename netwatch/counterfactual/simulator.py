"""
Counterfactual simulator.

For each defensive action:
  1. Modify the simulated current state (normalized vector).
  2. Feed the modified (history) into the World Model.
  3. Perform K-step rollout.
  4. Compute the resulting attack probability at each step via the learned
     risk head applied to each predicted state.

The no-action scenario is the natural model rollout. Every action's outcome is
thus a genuine model output — NOT a fixed percentage subtraction.
"""

import logging
from typing import Dict, List, Optional

import numpy as np

from netwatch.counterfactual.defensive_actions import DefensiveAction, _build_actions
from netwatch.models.base_model import WorldModel

logger = logging.getLogger(__name__)

# Interventions whose semantics remove the attacker's traffic entirely: the
# affected 30s window therefore reverts to typical benign traffic.
CONTAINMENT_ACTIONS = {
    "block_source", "block_dest_port", "isolate_host",
    "terminate_flow", "restrict_path",
}


class CounterfactualEngine:
    """Simulates defensive interventions and compares predicted futures."""

    def __init__(self, world_model: WorldModel, attack_forecaster,
                 normalizer, feature_columns: Optional[List[str]] = None):
        self.world_model = world_model
        self.attack_forecaster = attack_forecaster
        self.normalizer = normalizer
        self.feature_columns = feature_columns
        self._actions = None

    def _get_actions(self) -> Dict[str, DefensiveAction]:
        if self._actions is None:
            if self.feature_columns:
                self._actions = _build_actions(self.feature_columns)
            else:
                from netwatch.counterfactual.defensive_actions import ACTIONS
                self._actions = ACTIONS
        return self._actions

    def _risk_of_vector(self, vec: np.ndarray) -> float:
        return self.attack_forecaster._attack_prob(np.asarray(vec))

    def _neutralize(self, vec: np.ndarray) -> np.ndarray:
        """Return the vector under 'attacker traffic removed'."""
        profile = getattr(self.attack_forecaster, "benign_profile", None)
        if profile is not None:
            return np.asarray(profile, dtype=np.float64).copy()
        return vec

    def simulate(self, history_states, actions: Optional[List[str]] = None,
                 k: int = 5, feature_columns: Optional[List[str]] = None,
                 effect_window: int = 3) -> Dict:
        """
        Run counterfactual simulation for each action.
        """
        action_defs = _build_actions(feature_columns or self.feature_columns or [])
        actions = actions or list(action_defs.keys())
        if not history_states:
            return {"status": "no_history"}

        norm_history = [self.normalizer.transform(s) for s in history_states]
        current_vec = norm_history[-1].copy()
        baseline_current = self._risk_of_vector(current_vec)

        results: Dict[str, Dict] = {}
        for action_id in actions:
            if action_id not in action_defs:
                logger.warning(f"Unknown action {action_id}, skipping")
                continue
            action = action_defs[action_id]

            def _apply(vec, feats, _act=action, _aid=action_id):
                if _aid in CONTAINMENT_ACTIONS:
                    return self._neutralize(vec)
                return _act.apply(vec, feats)

            modified_history = list(norm_history)
            w = min(effect_window, len(norm_history))
            for j in range(len(norm_history) - w, len(norm_history)):
                vec = norm_history[j]
                feats = history_states[j].features
                modified_history[j] = _apply(vec, feats)

            risks = []
            horizon = list(modified_history)
            for _ in range(k):
                raw_vec = self.world_model.rollout(horizon, 1)[0]
                risks.append(self._risk_of_vector(raw_vec))
                horizon = horizon[1:] + [_apply(raw_vec, {})]

            final_risk = risks[-1]
            peak_risk = float(np.max(risks))

            results[action_id] = {
                "action_id": action_id,
                "label": action.label,
                "description": action.description,
                "final_risk": round(final_risk, 4),
                "peak_risk": round(peak_risk, 4),
                "risk_trajectory": [round(r, 4) for r in risks],
            }

        return {
            "status": "ok",
            "k": k,
            "effect_window": effect_window,
            "baseline_current_risk": round(baseline_current, 4),
            "results": results,
        }

    def recommend(self, simulation: Dict) -> Dict:
        """
        Choose the action that most reduces the predicted near-term attack
        exposure (peak risk over the simulated horizon) relative to no_action.
        """
        results = simulation.get("results", {})
        if not results:
            return {"status": "no_results"}

        no_action = results.get("no_action", {})
        baseline = no_action.get("peak_risk",
                                 simulation.get("baseline_current_risk", 0.0))

        best_action_id = None
        best_risk = float("inf")
        for action_id, r in results.items():
            if r["peak_risk"] < best_risk:
                best_risk = r["peak_risk"]
                best_action_id = action_id

        best = results[best_action_id]
        risk_reduction = round(baseline - best["peak_risk"], 4)

        if best_action_id != "no_action" and risk_reduction <= 0:
            best_action_id = "no_action"
            best = results["no_action"]
            risk_reduction = 0.0

        reason = (
            f"{best['label']} produces the largest reduction in predicted near-"
            f"term attack risk ({risk_reduction*100:.0f} percentage points, "
            f"peak risk {baseline*100:.0f}% to {best['peak_risk']*100:.0f}%) "
            f"among the simulated interventions."
        )

        return {
            "status": "ok",
            "recommended_action": best_action_id,
            "recommended_label": best["label"],
            "baseline_risk": round(baseline, 4),
            "counterfactual_risk": best["peak_risk"],
            "risk_reduction": risk_reduction,
            "risk_reduction_pct_points": round(risk_reduction * 100, 1),
            "reason": reason,
        }
