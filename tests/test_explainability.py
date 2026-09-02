"""Unit tests for explainability (SHAP + fallback path)."""

import numpy as np

from main.netwatch.config import FEATURE_COLUMNS
from main.netwatch.explainability.shap_explainer import ShapExplainer


def test_fallback_explains_without_model():
    exp = ShapExplainer(risk_model=None, feature_columns=FEATURE_COLUMNS)
    vec = np.zeros(len(FEATURE_COLUMNS))
    vec[6] = 1.0  # packets_per_second
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