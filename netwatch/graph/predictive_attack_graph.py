"""
Predictive attack graph.

Builds a directed graph of predicted attack-stage transitions with edge
probabilities derived from the World Model rollout. Node severity comes from the
stage risk impact; edge weights from the confidence of each predicted step.

All values are derived from the actual forecast, never fabricated.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

STAGE_SEVERITY = {
    "Reconnaissance": 1,
    "Initial Access": 3,
    "Execution": 4,
    "Lateral Movement": 5,
    "Command and Control": 6,
    "Exfiltration": 7,
    "Impact": 8,
    "Benign": 0,
}


def build_predictive_graph(forecast: Dict) -> Dict:
    """Convert a forecast report into a graph of predicted stage transitions.

    forecast: output of AttackForecaster.forecast() (has 'current' and 'future').
    Returns {nodes: [...], edges: [...]} consumable by a front-end graph view.
    """
    current = forecast.get("current", {})
    future = forecast.get("future", [])

    nodes: Dict[str, Dict] = {}
    edges = []

    # Current node
    cur_stage = current.get("stage", "Benign")
    nodes[cur_stage] = {
        "id": cur_stage,
        "label": cur_stage,
        "type": "current",
        "severity": STAGE_SEVERITY.get(cur_stage, 1),
        "risk": current.get("risk", 0.0),
        "probability": current.get("stage_probability", 0.0),
        "stage": cur_stage,
    }

    prev = cur_stage
    for step in future:
        step_stage = step.get("stage", "Benign")
        if step_stage not in nodes:
            nodes[step_stage] = {
                "id": step_stage,
                "label": step_stage,
                "type": "predicted",
                "severity": STAGE_SEVERITY.get(step_stage, 1),
                "risk": step.get("risk", 0.0),
                "probability": step.get("step_stage_prob", 0.0),
                "stage": step_stage,
                "step": step.get("step"),
            }
        edges.append({
            "source": prev,
            "target": step_stage,
            "weight": round(step.get("confidence", step.get("step_stage_prob", 0.0)), 4),
            "label": f"t+{step.get('step')}",
        })
        prev = step_stage

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "counts": {"nodes": len(nodes), "edges": len(edges)},
    }


def graph_to_json(graph: Dict) -> Dict:
    """Return a browser-friendly JSON structure (front-end expects same shape)."""
    return graph
