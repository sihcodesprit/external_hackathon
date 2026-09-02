"""Unit tests for the World Model interface, prediction and K-step rollout.

Uses the fast LinearWorldModel for rollout correctness and the LSTM model for
the interface/error paths (trained on tiny sequences).
"""

import numpy as np
import pytest

from main.netwatch.config import FEATURE_COLUMNS
from main.netwatch.models.base_model import WorldModelFactory
from main.netwatch.models.lstm_world_model import LSTMWorldModel


@pytest.fixture()
def linear():
    return WorldModelFactory.create("linear", n_features=len(FEATURE_COLUMNS))


@pytest.fixture()
def trained_linear(linear):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(64, 6, len(FEATURE_COLUMNS))).astype(np.float32)
    Y = rng.normal(size=(64, len(FEATURE_COLUMNS))).astype(np.float32)
    linear.fit(X, Y)
    return linear


def test_factory_unknown_model_raises():
    with pytest.raises(ValueError):
        WorldModelFactory.create("transformer_todo", n_features=5)


def test_linear_predict_shape(trained_linear):
    history = np.zeros((6, len(FEATURE_COLUMNS)), dtype=np.float32)
    pred = trained_linear.predict_next_state(history)
    assert pred.shape == (len(FEATURE_COLUMNS),)


def test_rollout_recursively_generates_k_states(trained_linear):
    history = [np.zeros(len(FEATURE_COLUMNS), dtype=np.float32)] * 6
    k = 5
    futures = trained_linear.rollout(history, k)
    assert len(futures) == k
    for vec in futures:
        assert np.asarray(vec).shape == (len(FEATURE_COLUMNS),)


def test_rollout_feed_back_does_not_change_inputs(trained_linear):
    history = [np.ones(len(FEATURE_COLUMNS), dtype=np.float32)] * 6
    snapshot = [h.copy() for h in history]
    trained_linear.rollout(history, 3)
    for a, b in zip(history, snapshot):
        np.testing.assert_array_equal(a, b)


def test_lstm_unfitted_raises_on_predict():
    model = LSTMWorldModel(n_features=len(FEATURE_COLUMNS))
    with pytest.raises(RuntimeError):
        model.predict_next_state(np.zeros((6, len(FEATURE_COLUMNS))))


def test_lstm_trains_and_rolls_out():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(32, 5, len(FEATURE_COLUMNS))).astype(np.float32)
    Y = rng.normal(size=(32, len(FEATURE_COLUMNS))).astype(np.float32)
    model = LSTMWorldModel(n_features=len(FEATURE_COLUMNS), hidden_size=16,
                           num_layers=1)
    info = model.fit(X, Y, epochs=1, batch_size=16)
    assert info["status"] == "trained"
    pred = model.predict_next_state(X[0])
    assert pred.shape == (len(FEATURE_COLUMNS),)
    futures = model.rollout(X[0], 3)
    assert len(futures) == 3


def test_save_load_roundtrip(tmp_path):
    rng = np.random.default_rng(2)
    X = rng.normal(size=(24, 5, len(FEATURE_COLUMNS))).astype(np.float32)
    Y = rng.normal(size=(24, len(FEATURE_COLUMNS))).astype(np.float32)
    model = LSTMWorldModel(n_features=len(FEATURE_COLUMNS), hidden_size=16,
                           num_layers=1)
    model.fit(X, Y, epochs=1, batch_size=12)
    path = tmp_path / "wm.pt"
    model.save(str(path))
    assert path.exists()

    loaded = LSTMWorldModel(n_features=len(FEATURE_COLUMNS))
    assert loaded.load(str(path)) is True
    before = model.predict_next_state(X[0])
    after = loaded.predict_next_state(X[0])
    np.testing.assert_allclose(before, after, atol=1e-6)


def test_load_missing_returns_false():
    model = LSTMWorldModel(n_features=len(FEATURE_COLUMNS))
    assert model.load("/nonexistent/path/model.pt") is False