"""
SHAP-based explainability.

Explains each forecast in terms of the top contributing network features.
Uses SHAP TreeExplainer / LinearExplainer on the learned risk head. When SHAP
or a trained risk head is unavailable, falls back to a transparent
feature-magnitude explanation (clearly labelled as a fallback, never passed off
as SHAP output).
"""

import logging
from typing import Dict, List

import numpy as np

from netwatch.config import FEATURE_COLUMNS

logger = logging.getLogger(__name__)


class ShapExplainer:
    """Generates feature-contribution explanations for a forecast."""

    def __init__(self, risk_model=None, feature_columns: List[str] = None,
                 normalizer=None):
        self.risk_model = risk_model
        self.feature_columns = feature_columns or FEATURE_COLUMNS
        self.normalizer = normalizer
        self._explainer = None
        self._shap_available = False
        if risk_model is not None:
            try:
                import shap  # noqa: F401
                self._shap_available = True
                self._build_explainer()
            except Exception as e:
                logger.warning(f"SHAP unavailable: {e}")

    def _build_explainer(self):
        try:
            import shap
            # shap 0.52 requires a masker for LinearExplainer
            masker = shap.maskers.Independent(np.zeros((1, len(self.feature_columns))))
            self._explainer = shap.LinearExplainer(self.risk_model, masker)
        except Exception as e:
            logger.warning(f"Could not build SHAP explainer: {e}")
            self._explainer = None

    def explain(self, state_vec_normalized: np.ndarray,
                features: Dict[str, float]) -> Dict:
        """
        Return sorted top contributing features for a given state.

        Returns:
            {
              "explanation_type": "shap" | "feature_magnitude",
              "contributions": [ {feature, contribution, sign}, ... ],
              "summary": "SYN rate (+0.31) drove the risk higher"
            }
        """
        vec = np.asarray(state_vec_normalized, dtype=np.float64).reshape(1, -1)

        if self._explainer is not None:
            try:
                values = self._explainer.shap_values(vec)
                vals = values[0]
                explanation_type = "shap"
            except Exception:
                vals = np.zeros_like(vec[0])
                explanation_type = "feature_magnitude"
        else:
            # Transparent magnitude fallback
            vals = np.abs(vec[0])
            explanation_type = "feature_magnitude"

        contributions = []
        for i, col in enumerate(self.feature_columns[:len(vals)]):
            v = float(vals[i])
            # direction: for SHAP use sign; for magnitude use sign of the raw
            # normalized value as the direction indicator.
            sign = "+" if (v >= 0 if explanation_type == "shap"
                           else vec[0][i] >= 0) else "-"
            contributions.append({
                "feature": col,
                "contribution": round(abs(v), 4),
                "sign": sign,
            })
        contributions.sort(key=lambda c: c["contribution"], reverse=True)

        top = contributions[:5]
        if top:
            first = top[0]
            summary = (
                f"{first['feature'].replace('_', ' ').title()} "
                f"({first['sign']}{first['contribution']:.2f}) was the "
                f"dominant factor in this forecast."
            )
        else:
            summary = "No dominant contributing feature identified."

        return {
            "explanation_type": explanation_type,
            "contributions": contributions,
            "top_features": top,
            "summary": summary,
        }
