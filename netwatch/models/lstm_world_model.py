"""
LSTM-based Cyber World Model.

Learns P(S_{t+1} | S_t) from temporal sequences of NetworkState vectors and can
recursively roll forward to produce K future states.

Architecture:
    history [seq_len x n_feat]
        -> feature projection (Linear)
        -> LSTM (stacked)
        -> latent network state (dense)
        -> next-state representation (Linear to n_feat)

The rollout() method feeds each predicted state back into the model as the new
last timestep, so future states are genuinely generated from previous predicted
states (not a repeated single probability). This was implemented with PyTorch
and requires no external inference service.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn

from netwatch.models.base_model import WorldModel

logger = logging.getLogger(__name__)


class LSTMNextState(nn.Module):
    """Sequence -> next-state neural module."""

    def __init__(self, n_features: int, hidden_size: int = 64,
                 num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.n_features = n_features
        self.projection = nn.Linear(n_features, hidden_size)
        self.lstm = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, n_features),
        )

    def forward(self, x):
        # x: (batch, seq_len, n_features)
        proj = torch.relu(self.projection(x))
        out, _ = self.lstm(proj)
        last = out[:, -1, :]  # take last hidden state (time step t)
        return self.head(last)


class LSTMWorldModel(WorldModel):
    """Concrete LSTM world model implementing the WorldModel interface."""

    def __init__(self, n_features: int, hidden_size: int = 64,
                 num_layers: int = 2, dropout: float = 0.2,
                 learning_rate: float = 1e-3, device=None):
        self.n_features = n_features
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = LSTMNextState(
            n_features, hidden_size, num_layers, dropout
        ).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.loss_fn = nn.MSELoss()
        self.is_trained = False
        self.sequence_length = None
        self.history = None  # rolling history for incremental prediction

    # ── training ───────────────────────────────────────────
    def fit(self, X, Y, batch_size: int = 32, epochs: int = 30,
            val_X=None, val_Y=None) -> Dict:
        X = torch.tensor(np.asarray(X, dtype=np.float32)).to(self.device)
        Y = torch.tensor(np.asarray(Y, dtype=np.float32)).to(self.device)
        self.sequence_length = X.shape[1]

        val_loss = float("nan")
        if val_X is not None and len(val_X):
            vX = torch.tensor(np.asarray(val_X, dtype=np.float32)).to(self.device)
            vY = torch.tensor(np.asarray(val_Y, dtype=np.float32)).to(self.device)

        self.model.train()
        n = X.shape[0]
        history = {"epochs": [], "train_loss": [], "val_loss": []}
        for epoch in range(epochs):
            perm = torch.randperm(n, device=self.device)
            epoch_loss = 0.0
            n_batches = 0
            for i in range(0, n, batch_size):
                idx = perm[i:i + batch_size]
                xb, yb = X[idx], Y[idx]
                self.optimizer.zero_grad()
                pred = self.model(xb)
                loss = self.loss_fn(pred, yb)
                loss.backward()
                self.optimizer.step()
                epoch_loss += loss.item()
                n_batches += 1

            train_loss = epoch_loss / max(n_batches, 1)
            history["epochs"].append(epoch + 1)
            history["train_loss"].append(train_loss)
            if val_X is not None and len(val_X):
                self.model.eval()
                with torch.no_grad():
                    vpred = self.model(vX)
                    val_loss = self.loss_fn(vpred, vY).item()
                self.model.train()
                history["val_loss"].append(val_loss)

        self.is_trained = True
        return {
            "status": "trained",
            "final_train_loss": history["train_loss"][-1],
            "final_val_loss": val_loss,
            "history": history,
            "model_type": "lstm",
            "device": self.device,
        }

    # ── inference helpers ──────────────────────────────────
    def _to_tensor(self, history) -> torch.Tensor:
        """history: list of vectors or array (seq_len, n_feat)."""
        arr = np.asarray(history, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.ndim != 2:
            raise ValueError("history must be 2D (seq_len, n_feat)")
        # pad/fix length to model.sequence_length
        seq_len = self.sequence_length or arr.shape[0]
        if arr.shape[0] < seq_len:
            pad = np.zeros((seq_len - arr.shape[0], arr.shape[1]), dtype=np.float32)
            arr = np.concatenate([pad, arr], axis=0)
        else:
            arr = arr[-seq_len:]
        t = torch.tensor(arr).unsqueeze(0).to(self.device)  # (1, seq_len, n_feat)
        return t

    def predict_next_state(self, history) -> np.ndarray:
        if not self.is_trained:
            raise RuntimeError("World model is not trained. Call fit() first.")
        self.model.eval()
        with torch.no_grad():
            pred = self.model(self._to_tensor(history))
        return pred.squeeze(0).cpu().numpy()

    def rollout(self, history, k: int) -> List[np.ndarray]:
        if not self.is_trained:
            raise RuntimeError("World model is not trained. Call fit() first.")
        self.model.eval()
        seq = list(np.asarray(history, dtype=np.float32))
        results = []
        with torch.no_grad():
            for _ in range(k):
                pred = self.model(self._to_tensor(seq))
                vec = pred.squeeze(0).cpu().numpy()
                results.append(vec)
                seq.append(vec)
                # maintain sequence length
                seq_len = self.sequence_length or len(seq)
                seq = seq[-seq_len:]
        self.history = seq
        return results

    def save(self, path: str):
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({
            "state_dict": self.model.state_dict(),
            "n_features": self.n_features,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "is_trained": self.is_trained,
            "sequence_length": self.sequence_length,
        }, path)
        logger.info(f"World model saved to {path}")

    def load(self, path: str) -> bool:
        import os
        if not os.path.exists(path):
            logger.warning(f"No checkpoint at {path}")
            return False
        try:
            ckpt = torch.load(path, map_location=self.device, weights_only=False)
        except TypeError:
            ckpt = torch.load(path, map_location=self.device)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to load checkpoint {path}: {e}")
            return False
        self.model = LSTMNextState(
            ckpt["n_features"],
            ckpt["hidden_size"],
            ckpt["num_layers"],
        ).to(self.device)
        self.model.load_state_dict(ckpt["state_dict"])
        self.is_trained = ckpt["is_trained"]
        self.sequence_length = ckpt.get("sequence_length")
        logger.info(f"World model loaded from {path}")
        self.is_trained = True
        return True
