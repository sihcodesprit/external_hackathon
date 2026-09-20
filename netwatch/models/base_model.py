"""
Abstract World Model interface.

Defines the contract every temporal world model must satisfy so that the LSTM,
and later alternatives (Transformer, Temporal Transformer, Temporal GNN), can be
swapped without rewriting the pipeline.

The core methods:

    train(...)
    predict_next_state(S_t)
    rollout(S_t, K)
    save(path)
    load(path)

The model learns and uses P(S_{t+1} | S_t). This is a genuine temporal model,
NOT a re-labelled classifier.
"""

from abc import ABC, abstractmethod
from typing import Dict


class WorldModel(ABC):
    """Interface for temporal network-state world models."""

    @abstractmethod
    def fit(self, X, Y, **kwargs) -> Dict:
        """Train on sequences X (N, seq_len, n_feat) -> next states Y."""
        ...

    @abstractmethod
    def predict_next_state(self, history):
        """Predict the next state given a history of normalized states.

        history: sequence of states / vectors ending at S_t.
        Returns: predicted normalized next-state vector.
        """
        ...

    @abstractmethod
    def rollout(self, history, k: int):
        """Recursively forecast k future states from the given history.

        Each predicted state is fed back as input for the next step.
        Returns a list of length k.
        """
        ...

    @abstractmethod
    def save(self, path: str):
        ...

    @abstractmethod
    def load(self, path: str) -> bool:
        ...


class WorldModelFactory:
    """Create a WorldModel by name (config-driven, swappable)."""

    @staticmethod
    def create(model_type: str, n_features: int, **kwargs) -> "WorldModel":
        if model_type == "lstm":
            from netwatch.models.lstm_world_model import LSTMWorldModel
            return LSTMWorldModel(n_features=n_features, **kwargs)
        if model_type == "linear":
            from netwatch.models.linear_world_model import LinearWorldModel
            return LinearWorldModel(n_features=n_features, **kwargs)
        raise ValueError(f"Unknown world model type: {model_type}")
