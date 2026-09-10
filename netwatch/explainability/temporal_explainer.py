"""
Temporal Explainability.

Tracks how feature contributions evolve across forecast steps (t+1 through t+K).
Unlike point-in-time SHAP (which explains a single state), this module answers
"which features are *changing* and driving risk evolution over time?" by
computing delta contributions between consecutive forecast states.

Uses the same SHAP / magnitude fallback as ShapExplainer but operates on
sequences of states rather than individual points.
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from netwatch.config import FEATURE_COLUMNS
from netwatch.explainability.shap_explainer import ShapExplainer

logger = logging.getLogger(__name__)


class TemporalExplainer:
    """Explains feature importance changes across a K-step forecast horizon."""

    def __init__(self, shap_explainer: Optional[ShapExplainer] = None,
                 feature_columns: Optional[List[str]] = None):
        self.shap_explainer = shap_explainer
        self.feature_columns = feature_columns or FEATURE_COLUMNS

    def _get_contributions(self, state_vec_normalized: np.ndarray) -> Dict[str, float]:
        """Get per-feature contributions for a single state."""
        if self.shap_explainer is not None:
            result = self.shap_explainer.explain(
                state_vec_normalized,
                {col: float(state_vec_normalized[i])
                 for i, col in enumerate(self.feature_columns[:len(state_vec_normalized)])}
            )
            return {c["feature"]: c["contribution"] * (1 if c["sign"] == "+" else -1)
                    for c in result["contributions"]}
        else:
            vec = np.asarray(state_vec_normalized, dtype=np.float64)
            return {col: float(vec[i]) for i, col in enumerate(self.feature_columns[:len(vec)])}

    def analyze(self, forecast_steps: List[Dict]) -> Dict:
        """
        Analyze feature importance evolution across forecast steps.

        Args:
            forecast_steps: list of step dicts from AttackForecaster.forecast()
                Each must have 'step', 'state_vec', 'risk', 'stage'.

        Returns:
            {
              "temporal_contributions": [per-step contribution dicts],
              "driving_features": {feature: [delta_per_step, ...]},
              "escalation_drivers": [features that increase risk most],
              "stabilization_drivers": [features that decrease risk most],
              "summary": "human-readable summary"
            }
        """
        if not forecast_steps:
            return {"status": "no_steps", "temporal_contributions": [],
                    "driving_features": {}, "escalation_drivers": [],
                    "stabilization_drivers": [], "summary": "No forecast steps to analyze."}

        step_contributions = []
        for step in forecast_steps:
            vec = np.asarray(step.get("state_vec", []), dtype=np.float64)
            if vec.size == 0:
                step_contributions.append({})
                continue
            contribs = self._get_contributions(vec)
            step_contributions.append(contribs)

        # Compute deltas between consecutive steps
        deltas: Dict[str, List[float]] = {f: [] for f in self.feature_columns}
        for i in range(1, len(step_contributions)):
            prev = step_contributions[i - 1]
            curr = step_contributions[i]
            for f in self.feature_columns:
                prev_val = prev.get(f, 0.0)
                curr_val = curr.get(f, 0.0)
                deltas[f].append(curr_val - prev_val)

        # Aggregate delta magnitudes across steps
        agg_deltas: Dict[str, float] = {}
        for f, d_list in deltas.items():
            if d_list:
                agg_deltas[f] = float(np.mean(np.abs(d_list)))
            else:
                agg_deltas[f] = 0.0

        # Sort by impact
        sorted_features = sorted(agg_deltas.items(), key=lambda x: x[1], reverse=True)
        driving_features = [f for f, _ in sorted_features if _ > 0][:10]

        # Escalation: features whose contributions increase (positive delta mean)
        escalation = []
        stabilization = []
        for f, d_list in deltas.items():
            if not d_list:
                continue
            mean_delta = float(np.mean(d_list))
            if mean_delta > 0:
                escalation.append((f, round(mean_delta, 4)))
            elif mean_delta < 0:
                stabilization.append((f, round(abs(mean_delta), 4)))

        escalation.sort(key=lambda x: x[1], reverse=True)
        stabilization.sort(key=lambda x: x[1], reverse=True)

        escalation_drivers = [f for f, _ in escalation[:5]]
        stabilization_drivers = [f for f, _ in stabilization[:5]]

        # Build per-step contribution summary
        temporal = []
        for i, contribs in enumerate(step_contributions):
            top = sorted(contribs.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
            temporal.append({
                "step": forecast_steps[i].get("step", i + 1),
                "risk": forecast_steps[i].get("risk"),
                "stage": forecast_steps[i].get("stage"),
                "top_features": [{"feature": f, "contribution": round(v, 4)} for f, v in top],
            })

        # Human-readable summary
        if escalation_drivers:
            esc_text = ", ".join(f.replace("_", " ") for f in escalation_drivers[:3])
            summary = (
                f"Risk escalation driven by: {esc_text}. "
            )
        else:
            summary = "No clear escalation drivers identified. "
        if stabilization_drivers:
            stab_text = ", ".join(f.replace("_", " ") for f in stabilization_drivers[:3])
            summary += f"Stabilizing factors: {stab_text}."
        else:
            summary += "No clear stabilization factors."

        return {
            "status": "ok",
            "temporal_contributions": temporal,
            "driving_features": {f: [round(d, 4) for d in deltas[f]]
                                 for f in driving_features},
            "escalation_drivers": escalation_drivers,
            "stabilization_drivers": stabilization_drivers,
            "feature_delta_summary": {f: round(agg_deltas[f], 4)
                                      for f in driving_features},
            "summary": summary,
        }
