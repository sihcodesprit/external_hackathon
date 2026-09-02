"""
Evaluation runner for the World Model.

Builds temporal train/test sequences from event data, trains the World Model,
and reports continuous + classification metrics, plus a comparison against
classical baseline classifiers (which operate on flattened windows and serve as
a sanity/baseline, not the primary model).
"""

import logging
from typing import Dict, List, Optional

import numpy as np

from main.netwatch.evaluation.metrics import evaluate_state_predictions
from main.netwatch.forecasting.stage_predictor import StagePredictor
from main.netwatch.models.baselines.benchmark import train_and_evaluate_baseline
from main.netwatch.models.trainer import WorldModelTrainer

logger = logging.getLogger(__name__)


class ModelEvaluator:
    """End-to-end evaluation of the World Model and baselines."""

    def __init__(self, trainer: WorldModelTrainer, normalizer):
        self.trainer = trainer
        self.normalizer = normalizer

    def evaluate(self, train_seqs, train_targets, test_seqs, test_targets,
                 bin_train=None, bin_test=None,
                 baseline_names=None) -> Dict:
        """train_seqs/test_seqs: arrays of normalized sequences (N, seq_len, f).

        train_targets/test_targets: continuous next-state vectors (N, f) used
        to evaluate the World Model's regression fit.
        bin_train/bin_test: (optional) binary attack labels (N,) used for the
        risk-projection classification metrics and baseline classifiers.
        """
        baseline_names = baseline_names or ["logreg", "random_forest"]

        # Training data for the World Model (continuous regression)
        train_X = np.asarray([s for s in train_seqs], dtype=np.float32)
        train_y = np.asarray([s for s in train_targets], dtype=np.float32)
        test_X = np.asarray([s for s in test_seqs], dtype=np.float32)
        test_y = np.asarray([s for s in test_targets], dtype=np.float32)

        world_result = self._evaluate_world(train_X, train_y, test_X, test_y,
                                            bin_test)

        # Baseline classification comparison on flattened window features
        flat_train_X = train_X.reshape(train_X.shape[0], -1)
        flat_test_X = test_X.reshape(test_X.shape[0], -1)
        baselines = {}
        if bin_train is not None and bin_test is not None and \
                len(np.unique(bin_train)) > 1:
            for name in baseline_names:
                try:
                    baselines[name] = train_and_evaluate_baseline(
                        name, flat_train_X, np.asarray(bin_train),
                        flat_test_X, np.asarray(bin_test))
                except Exception as e:
                    logger.warning(f"Baseline {name} failed: {e}")
                    baselines[name] = {"model": name, "error": str(e)}

        return {
            "world_model": world_result,
            "baselines": baselines,
            "n_train": len(train_X),
            "n_test": len(test_X),
            "note": "Evaluation on synthetic data. Real-dataset results marked "
                    "'Not evaluated yet' until such data is supplied.",
        }

    def _evaluate_world(self, train_X, train_y, test_X, test_y, bin_test):
        if not getattr(self.trainer.model, "is_trained", False):
            val_fraction = 0.15
            n = train_X.shape[0]
            split = int(n * (1 - val_fraction))
            X_tr, y_tr = train_X[:split], train_y[:split]
            X_va, y_va = train_X[split:], train_y[split:]
            self.trainer.fit(X_tr, y_tr, val_fraction=val_fraction,
                             batch_size=32, epochs=30)

        # one-step predictions on the test set
        pred_states = [self.trainer.model.predict_next_state(x)
                       for x in test_X]
        pred_states = np.asarray(pred_states)
        true_states = np.asarray(test_y)

        bin_labels = _safe_binary(bin_test) if bin_test is not None else \
            np.zeros(len(test_X), dtype=int)
        reg_cls = evaluate_state_predictions(
            pred_states, true_states, bin_labels, risk_head=None)

        return {
            "training_metrics": getattr(self.trainer, "last_metrics", {}),
            "prediction_metrics": reg_cls,
        }


def _safe_binary(labels: np.ndarray) -> np.ndarray:
    """Reshape labels to a 1D binary indicator if needed."""
    labels = np.asarray(labels)
    if labels.ndim == 2 and labels.shape[1] == 1:
        labels = labels.ravel()
    return labels
