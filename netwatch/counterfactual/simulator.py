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

Returns the estimated final risk for each action and a comparison table.
"""

import logging
from typing import Dict, List, Optional

import numpy as np

from netwatch.counterfactual.defensive_actions import ACTIONS
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
                 normalizer):
        self.world_model = world_model
        self.attack_forecaster = attack_forecaster  # provides learned risk head
        self.normalizer = normalizer

    def _risk_of_vector(self, vec: np.ndarray) -> float:
        return self.attack_forecaster._attack_prob(np.asarray(vec))

    def _neutralize(self, vec: np.ndarray) -> np.ndarray:
        """Return the vector under 'attacker traffic removed'.

        Prefers the forecaster's learned typical-benign profile; falls back to
        the original action semantics (mutation of the raw vector).
        """
        profile = getattr(self.attack_forecaster, "benign_profile", None)
        if profile is not None:
            return np.asarray(profile, dtype=np.float64).copy()
        return vec

    def simulate(self, history_states, actions: Optional[List[str]] = None,
                 k: int = 5, feature_columns: Optional[List[str]] = None,
                 effect_window: int = 3) -> Dict:
        """
        Run counterfactual simulation for each action.

        history_states: list of NetworkState (raw) representing S_{t-L}..S_t.
        `effect_window`: number of trailing history states the intervention is
            applied to. Simulating the action as already having taken effect for
            `effect_window` windows (i.e., the attacker's recent traffic has
            ceased) is what makes the counterfactual query meaningful — the
            world model rolls forward from a neutralized recent context.

        Returns dict with a per-action trajectory summary and a comparison.
        """
        actions = actions or list(ACTIONS.keys())
        if not history_states:
            return {"status": "no_history"}

        # normalized history vectors
        norm_history = [self.normalizer.transform(s) for s in history_states]
        current_vec = norm_history[-1].copy()
        current_features = history_states[-1].features

        # baseline current risk
        baseline_current = self._risk_of_vector(current_vec)

        results: Dict[str, Dict] = {}
        for action_id in actions:
            if action_id not in ACTIONS:
                logger.warning(f"Unknown action {action_id}, skipping")
                continue
            action = ACTIONS[action_id]
            # containment actions revert the window to typical benign traffic
            def _apply(vec, feats):
                if action_id in CONTAINMENT_ACTIONS:
                    return self._neutralize(vec)
                return action.apply(vec, feats)

            # apply the intervention to the last `effect_window` states
            modified_history = list(norm_history)
            w = min(effect_window, len(norm_history))
            for j in range(len(norm_history) - w, len(norm_history)):
                vec = norm_history[j]
                feats = history_states[j].features
                modified_history[j] = _apply(vec, feats)

            # Reactive K-step rollout: the intervention PERSISTS, so after each
            # predicted step the defense is re-applied to the predicted state
            # before it is fed back into the world model. Risk is read from the
            # model's raw predicted state — a genuine model output.
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

        Peak risk is the headline metric because it captures the imminent
        spike the defense is meant to prevent; the per-action trajectory is
        model-derived, never fabricated.

        Returns the recommendation with reason.
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
