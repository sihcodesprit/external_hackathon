"""Unit tests for explainability (SHAP + temporal + fallback path)."""

import numpy as np

from netwatch.config import FEATURE_COLUMNS
from netwatch.explainability.shap_explainer import ShapExplainer
from netwatch.explainability.temporal_explainer import TemporalExplainer


def test_fallback_explains_without_model():
    exp = ShapExplainer(risk_model=None, feature_columns=FEATURE_COLUMNS)
    vec = np.zeros(len(FEATURE_COLUMNS))
    vec[0] = 1.0  # total_packets
    result = exp.explain(vec, {})
    assert result["explanation_type"] == "feature_magnitude"
    assert len(result["contributions"]) == len(FEATURE_COLUMNS)
    assert len(result["top_features"]) == 5
    assert result["summary"]
    # contributions are sorted descending
    magnitudes = [c["contribution"] for c in result["contributions"]]
    assert magnitudes == sorted(magnitudes, reverse=True)


def test_top_feature_is_dominant():
    exp = ShapExplainer(risk_model=None, feature_columns=FEATURE_COLUMNS)
    vec = np.zeros(len(FEATURE_COLUMNS))
    vec[0] = 5.0  # strongest feature
    out = exp.explain(vec, {})
    assert out["top_features"][0]["feature"] == FEATURE_COLUMNS[0]
    assert out["top_features"][0]["contribution"] == 5.0


def test_explanation_with_risk_model_falls_back_gracefully():
    """Even when a risk model is supplied but SHAP init fails, explain() must
    still produce a meaningful result via the magnitude fallback."""
    class _BrokenRiskModel:
        pass
    exp = ShapExplainer(risk_model=_BrokenRiskModel(),
                        feature_columns=FEATURE_COLUMNS)
    vec = np.arange(len(FEATURE_COLUMNS), dtype=np.float64) * 0.5
    result = exp.explain(vec, {})
    assert "contributions" in result
    assert "top_features" in result
    assert "summary" in result


def test_temporal_explainer_empty_steps():
    tex = TemporalExplainer(feature_columns=FEATURE_COLUMNS)
    result = tex.analyze([])
    assert result["status"] == "no_steps"
    assert result["temporal_contributions"] == []
    assert result["summary"] == "No forecast steps to analyze."


def test_temporal_explainer_single_step():
    tex = TemporalExplainer(feature_columns=FEATURE_COLUMNS)
    steps = [{"step": 1, "state_vec": np.ones(len(FEATURE_COLUMNS)).tolist(),
              "risk": 0.5, "stage": "Execution"}]
    result = tex.analyze(steps)
    assert result["status"] == "ok"
    assert len(result["temporal_contributions"]) == 1
    assert result["temporal_contributions"][0]["step"] == 1
    assert result["temporal_contributions"][0]["risk"] == 0.5


def test_temporal_explainer_tracks_changing_features():
    tex = TemporalExplainer(feature_columns=FEATURE_COLUMNS)
    feat_idx = FEATURE_COLUMNS.index("packet_rate")
    vec1 = np.zeros(len(FEATURE_COLUMNS))
    vec2 = np.zeros(len(FEATURE_COLUMNS))
    vec2[feat_idx] = 2.0
    vec3 = np.zeros(len(FEATURE_COLUMNS))
    vec3[feat_idx] = 4.0
    steps = [
        {"step": 1, "state_vec": vec1.tolist(), "risk": 0.1, "stage": "Reconnaissance"},
        {"step": 2, "state_vec": vec2.tolist(), "risk": 0.3, "stage": "Initial Access"},
        {"step": 3, "state_vec": vec3.tolist(), "risk": 0.6, "stage": "Execution"},
    ]
    result = tex.analyze(steps)
    assert result["status"] == "ok"
    assert len(result["temporal_contributions"]) == 3
    assert "packet_rate" in result["escalation_drivers"]
    assert "packet_rate" in result["feature_delta_summary"]
