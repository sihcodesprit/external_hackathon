"""
Defensive recommendation engine.

Ranks defensive actions using:
  - predicted risk reduction
  - operational cost
  - business impact
  - asset criticality

Never automatically isolates critical infrastructure simply because it
produces the lowest model risk.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)

ACTION_COSTS = {
    "no_action": {"operational": 0, "business_impact": 0},
    "block_source": {"operational": 2, "business_impact": 1},
    "block_dest_port": {"operational": 3, "business_impact": 2},
    "isolate_host": {"operational": 5, "business_impact": 5},
    "terminate_flow": {"operational": 2, "business_impact": 2},
    "restrict_path": {"operational": 3, "business_impact": 3},
}

CRITICALITY_WEIGHTS = {
    "LOW": 1.0,
    "MEDIUM": 1.2,
    "HIGH": 1.5,
    "CRITICAL": 2.0,
}


class DefensiveRanker:
    """Ranks defensive actions based on risk reduction and operational constraints."""

    def __init__(self):
        pass

    def rank(self, simulation: Dict, asset_criticality: str = "LOW") -> Dict:
        """
        Rank actions from the counterfactual simulation.

        Returns ranked actions with scores.
        """
        results = simulation.get("results", {})
        baseline = simulation.get("baseline_current_risk", 0.0)
        crit_weight = CRITICALITY_WEIGHTS.get(asset_criticality, 1.0)

        ranked = []
        for action_id, result in results.items():
            risk_reduction = baseline - result.get("peak_risk", baseline)
            costs = ACTION_COSTS.get(action_id, {"operational": 3, "business_impact": 3})
            risk_score = max(0, risk_reduction * crit_weight)
            cost_penalty = (costs["operational"] + costs["business_impact"]) * 0.1
            recommendation_score = max(0, risk_score - cost_penalty)

            ranked.append({
                "action_id": action_id,
                "label": result.get("label", action_id),
                "description": result.get("description", ""),
                "peak_risk": result.get("peak_risk", 0),
                "risk_reduction": round(risk_reduction, 4),
                "operational_cost": costs["operational"],
                "business_impact": costs["business_impact"],
                "recommendation_score": round(recommendation_score, 4),
            })

        ranked.sort(key=lambda x: x["recommendation_score"], reverse=True)

        best = ranked[0] if ranked else None
        return {
            "ranked_actions": ranked,
            "best_action": best,
            "asset_criticality": asset_criticality,
        }
