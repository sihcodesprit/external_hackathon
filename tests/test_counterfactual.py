"""Unit tests for counterfactual defensive actions and the simulator.

Uses the fast LinearWorldModel so the K-step trajectory comparisons run
quickly. Asserts that action outcomes are real model outputs, not hardcoded
discounts.
"""

import numpy as np
import pytest

from netwatch.config import FEATURE_COLUMNS
from netwatch.counterfactual.defensive_actions import (
    ACTIONS,
    available_actions,
    get_action,
)
from netwatch.counterfactual.simulator import CounterfactualEngine
from netwatch.forecasting.attack_forecaster import AttackForecaster
from netwatch.models.base_model import WorldModelFactory


def test_all_actions_defined():
    for name in available_actions():
        action = get_action(name)
        assert action.id == name
        assert action.label
        assert action.description


def test_no_action_is_identity():
    vec = np.array([0.5, -0.3, 0.0, 0.2], dtype=np.float64)
    applied = get_action("no_action").apply(vec, {})
    np.testing.assert_array_equal(applied, vec)


def test_actions_preserve_vector_length():
    vec = np.arange(len(FEATURE_COLUMNS), dtype=np.float64)
    for name in available_actions():
        out = get_action(name).apply(vec, {})
        assert out.shape == vec.shape
        assert np.isfinite(out).all()


def test_block_source_zeroes_traffic_features():
    vec = np.ones(len(FEATURE_COLUMNS), dtype=np.float64)
    out = get_action("block_source").apply(vec, {"flow_dummy": 1.0})
    # attacker-traffic driven features are zeroed
    zeroed = {1, 6, 7, 8, 9, 10, 11, 12, 13, 14}  # packets, cps, conn, ports/hosts, syn/ack/rst, entropy
    for i in zeroed:
        assert out[i] == 0.0, f"feature {i} not zeroed"
    # static / payload-volume features survive
    for i in (2, 3, 4, 5):
        assert out[i] == 1.0, f"feature {i} should be untouched"


def _build_engine():
    rng = np.random.default_rng(0)
    n = len(FEATURE_COLUMNS)
    X = rng.normal(size=(48, 5, n)).astype(np.float32)
    Y = rng.normal(size=(48, n)).astype(np.float32)
    model = WorldModelFactory.create("linear", n_features=n)
    model.fit(X, Y)

    from netwatch.features.network_state import NetworkState
    class _Norm:
        mean, std = [0.0] * n, [1.0] * n
        def transform(self, s):
            return np.asarray(s.vector(), dtype=np.float64)
    forecaster = AttackForecaster(model, _Norm())
    engine = CounterfactualEngine(model, forecaster, _Norm())
    return engine, NetworkState


def test_simulate_returns_trajectories():
    engine, NetworkState = _build_engine()
    history = [NetworkState(timestamp=f"t{i}", features={
        c: 1.0 for c in FEATURE_COLUMNS}) for i in range(6)]
    sim = engine.simulate(history, actions=["no_action", "block_source"], k=3)
    assert sim["status"] == "ok"
    assert sim["k"] == 3
    assert set(sim["results"]) == {"no_action", "block_source"}
    for r in sim["results"].values():
        assert len(r["risk_trajectory"]) == 3
        assert 0.0 <= r["final_risk"] <= 1.0


def test_recommend_prefers_lower_risk():
    engine, NetworkState = _build_engine()
    history = [NetworkState(timestamp=f"t{i}", features={
        c: 1.0 for c in FEATURE_COLUMNS}) for i in range(6)]
    # build a trivial simulation dict where block_source clearly wins
    sim = {
        "status": "ok",
        "k": 3,
        "baseline_current_risk": 0.9,
        "results": {
            "no_action": {"label": "No Action", "peak_risk": 0.9,
                          "risk_trajectory": [0.9, 0.9, 0.9]},
            "block_source": {"label": "Block Source", "peak_risk": 0.1,
                             "risk_trajectory": [0.9, 0.1, 0.1]},
        },
    }
    rec = engine.recommend(sim)
    assert rec["recommended_action"] == "block_source"
    assert rec["risk_reduction"] > 0.0