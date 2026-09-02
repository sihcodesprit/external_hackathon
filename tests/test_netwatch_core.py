"""Focused tests for the netwatch Counterfactual Cyber World Model.

Kept fast: tiny traces, few training epochs.
"""

import numpy as np
import pytest

from main.netwatch.config import FEATURE_COLUMNS
from main.netwatch.ingestion.synthetic import generate_trace
from main.netwatch.features.network_state import StateBuilder
from main.netwatch.features.sequences import (
    StateNormalizer,
    assign_labels_and_stages,
    build_sequences,
    temporal_split,
)
from main.netwatch.forecasting.attack_forecaster import AttackForecaster
from main.netwatch.counterfactual.simulator import CounterfactualEngine
from main.netwatch.models.trainer import WorldModelTrainer


@pytest.fixture()
def states():
    from main.netwatch.pipeline import Pipeline
    pipe = Pipeline()
    pipe.load_data(n_traces=3, seed=7, duration_minutes=90)
    return pipe.states


def test_generator_labels_and_stages():
    records = generate_trace(duration_minutes=40, attack_bin_fraction=0.25,
                             packets_per_window=40, random_seed=3)
    assert len(records) > 0
    assert any(r.label == 1 for r in records)
    assert any(r.stage for r in records if r.label == 1)


def test_states_have_attack_ratio(states):
    labels = [int(s.label or 0) for s in states]
    frac = np.mean(labels)
    assert 0.05 < frac < 0.5, f"attack fraction {frac:.2f} out of range"


def test_all_stages_represented(states):
    stages = {s.stage for s in states if s.label == 1}
    assert stages == {"Reconnaissance", "Initial Access", "Execution",
                      "Lateral Movement", "Command and Control", "Exfiltration"}


def test_temporal_split_is_balanced(states):
    train, val = temporal_split(states, 0.2)
    ftr = np.mean([s.label for s in train])
    fva = np.mean([s.label for s in val])
    assert ftr > 0.05 and fva > 0.05, f"train {ftr:.2f} val {fva:.2f}"


def test_normalizer_roundtrip(states):
    norm = StateNormalizer()
    norm.fit(states)
    vec = norm.transform(states[0])
    assert vec.shape == (len(norm.mean),)
    restored = vec * np.asarray(norm.std) + np.asarray(norm.mean)
    feats = states[0].features
    for i, col in enumerate(FEATURE_COLUMNS):
        assert restored[i] == pytest.approx(feats[col], abs=1e-3)


def test_build_sequences_shapes(states):
    norm = StateNormalizer()
    norm.fit(states)
    X, Y = build_sequences(states, normalizer=norm,
                           sequence_length=6, horizon=2)
    assert X.shape[1] == 6 and X.shape[2] == len(states[0].features)
    assert Y.shape[1] == len(states[0].features)


def test_trainer_learns(states):
    norm = StateNormalizer()
    norm.fit(states)
    seq, tgt = build_sequences(states, normalizer=norm,
                               sequence_length=6, horizon=1)
    trainer = WorldModelTrainer(n_features=len(states[0].features))
    info = trainer.fit(seq, tgt, epochs=2, batch_size=32)
    assert info["status"] == "trained"
    assert trainer.model.is_trained


def test_counterfactual_meaningful(states):
    norm = StateNormalizer()
    norm.fit(states)
    trainer = WorldModelTrainer(n_features=len(states[0].features))
    seq, tgt = build_sequences(states, normalizer=norm,
                               sequence_length=6, horizon=1)
    trainer.fit(seq, tgt, epochs=3, batch_size=32)

    forecaster = AttackForecaster(trainer.model, norm)
    forecaster.fit_risk_head(states)

    # window ending in an ongoing attack
    attack_idx = None
    for i in range(len(states) - 2, -1, -1):
        if states[i].label == 1 and states[i + 1].label == 1:
            attack_idx = i
            break
    assert attack_idx is not None
    history = states[attack_idx - 5:attack_idx + 1]

    engine = CounterfactualEngine(trainer.model, forecaster, norm)
    sim = engine.simulate(history, actions=["no_action", "block_source"], k=4)
    rec = engine.recommend(sim)
    assert sim["status"] == "ok"
    assert rec["status"] == "ok"
    na = sim["results"]["no_action"]["risk_trajectory"]
    bs = sim["results"]["block_source"]["risk_trajectory"]
    # containment must meaningfully reduce the model's predicted risk
    assert np.mean(na) > np.mean(bs) + 0.1, (np.mean(na), np.mean(bs))
    assert rec["recommended_label"] in {"No Action", "Block Source"}


def test_dashboard_app_routes():
    from main.netwatch.dashboard.app import app
    client = app.test_client()
    for path in ("/dashboard", "/radar", "/graph", "/counterfactual",
                 "/stages", "/explainability", "/evaluation", "/scenarios"):
        resp = client.get(path)
        assert resp.status_code == 200