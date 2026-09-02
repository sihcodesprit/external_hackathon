"""
Model trainer: fit a WorldModel from temporal sequences with a temporal split.

Encapsulates the training loop so the pipeline and dashboard can reuse it.
"""

import logging
from typing import Dict, Optional

from main.netwatch.config import BATCH_SIZE, NUM_EPOCHS, TRAIN_VAL_SPLIT
from main.netwatch.models.base_model import WorldModel, WorldModelFactory

logger = logging.getLogger(__name__)


class WorldModelTrainer:
    """Fits and saves a WorldModel."""

    def __init__(self, model: Optional[WorldModel] = None,
                 model_type: str = "lstm", n_features: int = 15,
                 **model_kwargs):
        if model is None:
            model = WorldModelFactory.create(
                model_type, n_features=n_features, **model_kwargs
            )
        self.model = model
        self.model_type = model_type
        self.last_metrics: Dict = {}

    def fit(self, X, y, val_fraction: float = TRAIN_VAL_SPLIT,
            batch_size: int = BATCH_SIZE, epochs: int = NUM_EPOCHS) -> Dict:
        # temporal split (no shuffle) on the sequence axis
        n = X.shape[0]
        split = int(n * (1 - val_fraction))
        X_train, y_train = X[:split], y[:split]
        X_val, y_val = X[split:], y[split:]

        metrics = self.model.fit(
            X_train, y_train,
            batch_size=batch_size, epochs=epochs,
            val_X=X_val, val_Y=y_val,
        )
        metrics["train_sequences"] = X_train.shape[0]
        metrics["val_sequences"] = X_val.shape[0]
        self.last_metrics = metrics
        return metrics

    def save(self, path: str):
        self.model.save(path)

    def load(self, path: str) -> bool:
        return self.model.load(path)
