"""
Temporal sequence dataset construction.

Converts a list of NetworkState into supervised sequences:

    [S(t-4), S(t-3), S(t-2), S(t-1), S(t)]  ->  S(t+1)

Splitting is TEMPORAL / SESSION-AWARE (not random row-level) to avoid leakage:
the train/val split is done on the time axis (i.e. earlier sessions train,
later sessions validate), and optional unseen-attack separation holds out
entire attack types / sessions.

Also builds a label (attack/benign) per state and per (+1) target for the
baseline classifiers and stage predictor.
"""

import logging
import pickle
from typing import Dict, List, Optional, Tuple

import numpy as np

from netwatch.config import SEQUENCE_LENGTH, get_feature_columns
from netwatch.features.network_state import NetworkState

logger = logging.getLogger(__name__)


class StateNormalizer:
    """Fits mean/std on training states and transforms to normalized vectors."""

    def __init__(self):
        self.mean: List[float] = []
        self.std: List[float] = []
        self._fitted = False

    def fit(self, states: List[NetworkState]):
        X = np.array([s.vector() for s in states], dtype=np.float64)
        if X.shape[0] == 0:
            cols = get_feature_columns()
            self.mean = [0.0] * len(cols)
            self.std = [1.0] * len(cols)
        else:
            self.mean = X.mean(axis=0).tolist()
            self.std = X.std(axis=0).tolist()
        # guard against zero variance
        self.std = [s if s > 1e-6 else 1.0 for s in self.std]
        self._fitted = True
        return self

    def transform(self, state: NetworkState) -> np.ndarray:
        vec = np.asarray(state.vector(), dtype=np.float64)
        return (vec - np.asarray(self.mean)) / np.asarray(self.std)

    def save(self, path):
        with open(path, "wb") as f:
            pickle.dump({"mean": self.mean, "std": self.std}, f)

    @classmethod
    def load(cls, path) -> "StateNormalizer":
        with open(path, "rb") as f:
            data = pickle.load(f)
        n = cls()
        n.mean = data["mean"]
        n.std = data["std"]
        n._fitted = True
        return n


def assign_labels_and_stages(
    states: List[NetworkState],
    stage_vocab: List[str],
    attack_sessions: Optional[Dict[str, str]] = None,
) -> List[NetworkState]:
    """
    Assign a binary attack label and a MITRE stage to each state.

    Without ground-truth labels (as with synthetic data), a state is labelled
    "attack" if its traffic profile is anomalous (e.g. high SYN rate / port
    entropy / low normal). When real datasets provide labels, they should be
    propagated here instead.

    attack_sessions: optional dict mapping src_ip -> stage for labelled traces.
    """
    from netwatch.forecasting.stage_predictor import heuristic_stage

    for s in states:
        f = s.features
        # Prefer existing ground-truth labels (from synthetic generator /
        # labelled datasets); fall back to a documented heuristic profile.
        if s.label is None:
            is_attack = (
                f["syn_rate"] >= 0.5
                or f["port_entropy"] >= 1.0
                or f["packets_per_second"] >= 15.0
                or f["unique_dst_ports"] >= 8
            )
            s.label = 1 if is_attack else 0
        # Stage: prefer provided mapping / existing ground truth, else heuristic
        if s.stage is None:
            stage = None
            if attack_sessions and s.src_ip in attack_sessions:
                stage = attack_sessions[s.src_ip]
            else:
                stage = heuristic_stage(f)
            s.stage = stage
    return states


def build_sequences(
    states: List[NetworkState],
    normalizer: StateNormalizer,
    sequence_length: int = SEQUENCE_LENGTH,
    horizon: int = 1,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build (input_sequences, targets) numpy arrays.

    input:  (N, sequence_length, n_features) normalized past states
    target: (N, n_features) normalized next state  [+ optional label handled
            separately via state.label]
    """
    X, Y = [], []
    vecs = [normalizer.transform(s) for s in states]
    for i in range(len(states) - sequence_length - horizon + 1):
        X.append(vecs[i:i + sequence_length])
        Y.append(vecs[i + sequence_length + horizon - 1])
    if not X:
        cols = get_feature_columns()
        return np.zeros((0, sequence_length, len(cols))), \
               np.zeros((0, len(cols)))
    return np.asarray(X, dtype=np.float32), np.asarray(Y, dtype=np.float32)


def build_seq_labels(states: List[NetworkState],
                     sequence_length: int = SEQUENCE_LENGTH,
                     horizon: int = 1) -> np.ndarray:
    """
    Build binary attack labels aligned with build_sequences() rows.

    The target state for row i is S[i + sequence_length + horizon - 1], so the
    label is that state's ground-truth label.
    """
    labels = []
    for i in range(len(states) - sequence_length - horizon + 1):
        labels.append(int(states[i + sequence_length + horizon - 1].label or 0))
    return np.asarray(labels, dtype=int)


def temporal_split(
    states: List[NetworkState],
    val_fraction: float = 0.2,
) -> Tuple[List[NetworkState], List[NetworkState]]:
    """
    Temporal / session-aware split: sort by time, take the first (1-val_fraction)
    share as train and the last val_fraction as validation. No shuffling.
    """
    ordered = sorted(states, key=lambda s: s.timestamp)
    n = len(ordered)
    split = int(n * (1 - val_fraction))
    return ordered[:split], ordered[split:]


def split_by_group(
    states: List[NetworkState],
    key_fn,
    val_key,
) -> Tuple[List[NetworkState], List[NetworkState]]:
    """
    Split by a group key (e.g. attacker IP or attack session) so that a whole
    group appears entirely in one side. Used for unseen-attack evaluation.
    """
    train, val = [], []
    for s in states:
        (train if key_fn(s) != val_key else val).append(s)
    return train, val
