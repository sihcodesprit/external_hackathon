"""
Predictive attack graph.

Builds a directed graph of predicted attack-stage transitions with edge
weights derived from the World Model rollout confidence. Node severity comes
from the stage risk impact, edge weights from the confidence of each
predicted step.

The graph preserves EVERY forecast step as a timeline node while also
providing a stage-collapsed view (consecutive identical stages collapsed)
with correctly computed transition counts. All values are derived from the
actual forecast, never fabricated.
"""

import logging
from typing import Any, Dict, List, Optional

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


def _finite(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return f


def _stage(value: Any) -> str:
    s = str(value or "").strip()
    return s if s else "Unknown"


def build_predictive_graph(forecast: Dict) -> Dict:
    """Convert a forecast report into a graph of predicted stage transitions.

    forecast: output of AttackForecaster.forecast() (has 'current' and 'future').

    Returns a dict consumable by the front-end graph view:
      nodes  — one node per timeline entry (step 0 = current, then t+1..t+k),
               ids are stable ("t0", "t1", ...) so React keys stay stable.
      edges  — consecutive timeline transitions, weight = forecast confidence.
      timeline — every forecast step preserved (step, stage, risk, confidence).
      stages — ordered unique stage list along the trajectory.
      stage_nodes / stage_edges — consecutive-equivalent stages collapsed into
               a readable stage-transition graph.
      counts — {nodes, edges, forecast_steps, stages, transitions} where
               'transitions' counts actual stage changes (repeated identical
               stages are not transitions).
    """
    current = forecast.get("current", {}) if isinstance(forecast, dict) else {}
    if not isinstance(current, dict):
        current = {}
    future = forecast.get("future", []) if isinstance(forecast, dict) else []
    if not isinstance(future, list):
        future = []

    cur_stage = _stage(current.get("stage"))

    timeline: List[Dict[str, Any]] = []
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    unique_stages: List[str] = []

    def _register_stage(stage: str) -> None:
        if stage not in unique_stages:
            unique_stages.append(stage)

    # Current node (timeline step 0)
    _register_stage(cur_stage)
    cur_risk = _finite(current.get("risk"))
    cur_prob = _finite(current.get("stage_probability"))
    nodes.append({
        "id": "t0",
        "label": cur_stage,
        "stage": cur_stage,
        "type": "current",
        "severity": STAGE_SEVERITY.get(cur_stage, 1),
        "risk": round(cur_risk, 4),
        "confidence": round(_finite(current.get("confidence"), cur_prob), 4),
        "probability": round(cur_prob, 4),
        "step": 0,
        "evidence": [],
    })
    timeline.append({
        "step": 0,
        "stage": cur_stage,
        "risk": round(cur_risk, 4),
        "confidence": round(_finite(current.get("confidence"), cur_prob), 4),
        "probability": round(cur_prob, 4),
    })

    prev_id = "t0"
    for s in future:
        if not isinstance(s, dict):
            continue
        step = int(_finite(s.get("step"), len(nodes)))
        stage = _stage(s.get("stage"))
        risk = round(_finite(s.get("risk")), 4)
        prob = round(_finite(s.get("step_stage_prob"), s.get("stage_probability")), 4)
        conf = round(_finite(s.get("confidence"), prob), 4)
        node_id = f"t{step}"
        evidence = s.get("supporting_features") or []
        if not isinstance(evidence, list):
            evidence = []

        _register_stage(stage)
        nodes.append({
            "id": node_id,
            "label": stage,
            "stage": stage,
            "type": "predicted",
            "severity": STAGE_SEVERITY.get(stage, 1),
            "risk": risk,
            "confidence": conf,
            "probability": prob,
            "step": step,
            "evidence": evidence,
        })
        timeline.append({
            "step": step,
            "stage": stage,
            "risk": risk,
            "confidence": conf,
            "probability": prob,
        })
        edges.append({
            "id": f"{prev_id}->{node_id}",
            "source": prev_id,
            "target": node_id,
            "weight": conf,
            "label": f"t+{step}",
            "transition": stage != timeline[-2]["stage"],
        })
        prev_id = node_id

    # Stage-collapsed view: collapse consecutive identical stages.
    stage_nodes: List[Dict[str, Any]] = []
    stage_edges: List[Dict[str, Any]] = []
    prev_stage: Optional[str] = None
    prev_stage_id: Optional[str] = None
    for n in nodes:
        if n["stage"] != prev_stage:
            sid = f"sg{len(stage_nodes)}"
            stage_nodes.append({**n, "id": sid, "collapsed": False})
            if prev_stage_id is not None and prev_stage is not None:
                stage_edges.append({
                    "id": f"{prev_stage_id}->{sid}",
                    "source": prev_stage_id,
                    "target": sid,
                    "weight": n.get("confidence", 0.0),
                    "label": "predicted transition",
                    "transition": True,
                })
            prev_stage = n["stage"]
            prev_stage_id = sid

    transitions = sum(1 for e in edges if e.get("transition"))

    return {
        "nodes": nodes,
        "edges": edges,
        "timeline": timeline,
        "stages": unique_stages,
        "stage_nodes": stage_nodes,
        "stage_edges": stage_edges,
        "benign_only": len(unique_stages) == 1 and unique_stages[0] == "Benign",
        "unknown_stage": any(stg == "Unknown" for stg in unique_stages),
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "forecast_steps": len(future),
            "stages": len(unique_stages),
            "transitions": transitions,
        },
    }


def graph_to_json(graph: Dict) -> Dict:
    """Return a browser-friendly JSON structure (front-end expects same shape)."""
    return graph
