"""
Forecasting evaluation metrics.

Because the World Model is a continuous next-state predictor, we evaluate it
with continuous regression metrics on the normalized feature space. Then, to
compare with classical attack classifiers, we project predicted/states onto
binary attack risk using the learned risk head and compute classification
metrics. Everything is computed on actual predictions.
"""

import logging
from typing import Dict, List

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
    """Continuous metrics on predicted next-state vectors."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(np.sqrt(mse))
    mae = float(mean_absolute_error(y_true, y_pred))
    # cosine similarity of flattened vectors
    cos = _cosine(y_true.reshape(len(y_true), -1),
                  y_pred.reshape(len(y_pred), -1))
    return {
        "mse": round(mse, 5),
        "rmse": round(rmse, 5),
        "mae": round(mae, 5),
        "mean_cosine": round(float(np.nanmean(cos)), 4),
    }


def _cosine(a, b):
    dot = np.sum(a * b, axis=1)
    na = np.linalg.norm(a, axis=1) + 1e-9
    nb = np.linalg.norm(b, axis=1) + 1e-9
    return dot / (na * nb)


def classification_metrics(y_true: np.ndarray, risk_pred: np.ndarray,
                           threshold: float = 0.5) -> Dict:
    """Binary metrics from continuous risk + threshold."""
    y_true = np.asarray(y_true)
    y_pred_bin = (np.asarray(risk_pred) >= threshold).astype(int)
    metrics = {
        "accuracy": round(accuracy_score(y_true, y_pred_bin), 4),
        "precision": round(precision_score(y_true, y_pred_bin, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred_bin, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred_bin, zero_division=0), 4),
        "threshold": threshold,
    }
    if len(np.unique(y_true)) > 1:
        try:
            metrics["roc_auc"] = round(
                float(roc_auc_score(y_true, np.asarray(risk_pred))), 4)
        except ValueError:
            metrics["roc_auc"] = float("nan")
    return metrics


def evaluate_state_predictions(pred_states: List[np.ndarray],
                               true_states: List[np.ndarray],
                               true_labels: List[int],
                               risk_head=None) -> Dict:
    """Run both continuous and classification evaluation on one test set.

    pred_states: predicted next-state (normalized) vectors.
    true_states: actual next-state vectors.
    true_labels: actual binary attack labels (0 benign / 1 attack).
    risk_head: callable state -> risk, or None to use magnitude fallback.
    """
    pred_states = np.asarray(pred_states, dtype=np.float64)
    true_states = np.asarray(true_states, dtype=np.float64)

    reg = regression_metrics(true_states, pred_states)

    # classification via risk head (or magnitude fallback)
    if risk_head is not None:
        risks = [float(risk_head(p)) for p in pred_states]
    else:
        risks = [float(min(np.linalg.norm(p) / 8.0, 1.0)) for p in pred_states]

    cls = classification_metrics(true_labels, risks)

    return {"continuous": reg, "classification": cls, "risk_scores": risks}
