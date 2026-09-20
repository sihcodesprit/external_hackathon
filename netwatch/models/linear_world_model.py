"""
Baseline World Model: a linear next-state regressor used to sanity-check the
LSTM. Provided mainly for testing the abstract interface without a neural net.
"""

import logging

import numpy as np

from netwatch.models.base_model import WorldModel

logger = logging.getLogger(__name__)


class LinearWorldModel(WorldModel):
    """Simple linear next-state predictor (baseline world model)."""

    def __init__(self, n_features: int, **kwargs):
        self.n_features = n_features
        # aggregator: mean over time -> linear mapping to next state
        self.W = None
        self.is_trained = False
        self.sequence_length = None

    def fit(self, X, Y, **kwargs) -> dict:
        arr = np.asarray(X, dtype=np.float64)
        T = arr.mean(axis=1)  # (N, n_feat)
        Y = np.asarray(Y, dtype=np.float64)
        # ridge regression (regularized)
        reg = kwargs.get("alpha", 1e-2)
        A = T.T @ T + reg * np.eye(self.n_features)
        b = T.T @ Y
        self.W = np.linalg.solve(A, b)
        self.sequence_length = arr.shape[1]
        self.is_trained = True
        return {"status": "trained", "model_type": "linear"}

    def _aggregate(self, history) -> np.ndarray:
        arr = np.asarray(history, dtype=np.float64)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr.mean(axis=0)

    def predict_next_state(self, history) -> np.ndarray:
        return self._aggregate(history) @ self.W

    def rollout(self, history, k: int) -> list:
        results = []
        seq = list(np.asarray(history, dtype=np.float32))
        for _ in range(k):
            pred = self.predict_next_state(seq)
            results.append(pred)
            seq.append(pred)
            seq = seq[-self.sequence_length:]
        return results

    def save(self, path: str):
        import json
        import os

        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "W": self.W.tolist() if self.W is not None else None,
            "n_features": self.n_features,
            "sequence_length": self.sequence_length
        }
        with open(path, "w") as f:
            json.dump(data, f)

    def load(self, path: str) -> bool:
        import json
        import os

        import numpy as np
        if not os.path.exists(path):
            return False
        with open(path, "r") as f:
            d = json.load(f)
        self.W = np.array(d["W"], dtype=np.float64) if d["W"] is not None else None
        self.sequence_length = d["sequence_length"]
        self.is_trained = True
        return True
