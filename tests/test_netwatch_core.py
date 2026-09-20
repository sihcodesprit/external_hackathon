from datetime import datetime, timedelta

import numpy as np
import pytest

from netwatch.config import get_feature_columns
from netwatch.counterfactual.simulator import CounterfactualEngine
from netwatch.features.sequences import (
    StateNormalizer,
    build_sequences,
    temporal_split,
)
from netwatch.forecasting.attack_forecaster import AttackForecaster
from netwatch.ingestion.parser import PacketRecord
from netwatch.models.trainer import WorldModelTrainer


@pytest.fixture()
def test_records():
    base = datetime(2026, 9, 1, 12, 0, 0)
    records = []
    for i in range(120):
        ts = (base + timedelta(seconds=i * 2)).isoformat() + "Z"
        stage = "Reconnaissance" if i < 40 else "Initial Access" if i < 80 else "Exfiltration"
        label = 1 if i % 3 != 0 else 0
        records.append(PacketRecord(
            timestamp=ts,
            src_ip="192.168.1.100" if label == 1 else "192.168.1.5",
            dst_ip="10.0.0.1",
            src_port=40000 + i,
            dst_port=80 if i % 2 == 0 else 443,
            protocol="TCP",
            flags="S" if i < 40 else "A",
            bytes_sent=100 + i * 5,
            payload_size=50 if i < 40 else 800,
            ttl=64,
            tcp_window=65535,
            duration=0.1,
            label=label,
            stage=stage if label == 1 else "",
        ))
    return records


@pytest.fixture()
def states(test_records):
    from netwatch.pipeline import Pipeline
    pipe = Pipeline()
    pipe.load_data(records=test_records)
    return pipe.states


def test_packet_records_and_stages(test_records):
    assert len(test_records) > 0
    assert any(r.label == 1 for r in test_records)
    assert any(r.stage for r in test_records if r.label == 1)


def test_states_have_attack_ratio(states):
    labels = [int(s.label or 0) for s in states]
    frac = np.mean(labels)
    assert 0.05 < frac < 0.95, f"attack fraction {frac:.2f} out of range"


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
    feature_cols = get_feature_columns()
    # Only check columns that exist in the state features
    for i, col in enumerate(feature_cols):
        if col in feats:
            assert restored[i] == pytest.approx(feats[col], abs=1e-3), f"Mismatch for {col}: {restored[i]} vs {feats[col]}"


def test_build_sequences_shapes(states):
    norm = StateNormalizer()
    norm.fit(states)
    X, Y = build_sequences(states, normalizer=norm,
                           sequence_length=6, horizon=2)
    assert X.shape[1] == 6 and X.shape[2] == len(states[0].vector())
    assert Y.shape[1] == len(states[0].vector())


def test_trainer_learns(states):
    norm = StateNormalizer()
    norm.fit(states)
    seq, tgt = build_sequences(states, normalizer=norm,
                               sequence_length=6, horizon=1)
    trainer = WorldModelTrainer(n_features=len(states[0].vector()))
    info = trainer.fit(seq, tgt, epochs=2, batch_size=32)
    assert info["status"] == "trained"
    assert trainer.model.is_trained


def test_counterfactual_meaningful(states):
    norm = StateNormalizer()
    norm.fit(states)
    trainer = WorldModelTrainer(n_features=len(states[0].vector()))
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
    assert np.mean(na) > np.mean(bs), f"no_action {np.mean(na)} should be > block_source {np.mean(bs)}"
    assert rec["recommended_label"] in {"No Action", "Block Source"}


def test_dashboard_app_routes():
    from netwatch.dashboard.app import app
    client = app.test_client()
    for path in ("/dashboard", "/radar", "/graph", "/counterfactual",
                 "/stages", "/explainability", "/evaluation", "/scenarios"):
        resp = client.get(path)
        assert resp.status_code == 200
