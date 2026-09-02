"""
Unseen-attack generalization test.

Evaluates whether the World Model / risk head generalizes to an attack pattern
NOT seen during training. This ensures we are not simply memorizing the
training distribution.

Synthetic data supports this by generating attack traces with a held-out
technique whose stage/frequency profile differs from the training set.
"""

import logging
from typing import Dict, List, Optional

import numpy as np

from main.netwatch.evaluation.metrics import evaluate_state_predictions
from main.netwatch.models.trainer import WorldModelTrainer

logger = logging.getLogger(__name__)


class UnseenAttackTest:
    """Measures generalization to an uns  een attack scenario."""

    def __init__(self, trainer: WorldModelTrainer, normalizer):
        self.trainer = trainer
        self.normalizer = normalizer

    def run(self, train_seqs, train_targets, unseen_seqs, unseen_targets,
            bin_unseen=None, unseen_true_states=None) -> Dict:
        """
        train_*: sequences/labels the model learned from.
        unseen_*: sequences/targets from an attack technique absent from
                  training. bin_unseen: binary attack labels for unseen rows.

        Reports prediction quality on the unseen attack. All numbers are
        computed on actual predictions (no fabrication).
        """
        train_X = np.asarray([s for s in train_seqs], dtype=np.float32)
        train_y = np.asarray([s for s in train_targets], dtype=np.float32)
        unseen_X = np.asarray([s for s in unseen_seqs], dtype=np.float32)
        unseen_y = np.asarray([s for s in unseen_targets], dtype=np.float32)

        # train the world model (already-trained models are reused if is_trained)
        if not getattr(self.trainer.model, "is_trained", False):
            self.trainer.fit(train_X, train_y, val_fraction=0.1,
                             batch_size=32, epochs=20)

        pred_states = [self.trainer.model.predict_next_state(x)
                       for x in unseen_X]
        pred_states = np.asarray(pred_states)
        true_states = (unseen_true_states if unseen_true_states is not None
                       else unseen_y)
        bin_labels = (_safe_binary(bin_unseen) if bin_unseen is not None
                      else np.zeros(len(unseen_X), dtype=int))

        metrics = evaluate_state_predictions(pred_states, true_states,
                                             bin_labels, risk_head=None)
        metrics["n_unseen"] = len(unseen_X)
        metrics["note"] = (
            "Generalization measured on an attack pattern withheld from "
            "training (synthetic). Real-dataset generalization not yet evaluated."
        )
        return metrics


def _safe_binary(labels: np.ndarray) -> np.ndarray:
    labels = np.asarray(labels)
    if labels.ndim == 2 and labels.shape[1] == 1:
        labels = labels.ravel()
    return labels
