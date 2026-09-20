"""Tests for Ensemble Threat Scorer and multi-engine consensus."""

import pytest

from netwatch.features.network_state import NetworkState
from netwatch.forecasting.ensemble_scorer import EnsembleScorer
from netwatch.pipeline import Pipeline


@pytest.fixture(scope="module")
def pipeline():
    """Train a lightweight pipeline once for the test module."""
    pipe = Pipeline()
    pipe.load_data(n_traces=2, seed=42, duration_minutes=40.0)
    # Fast training for tests
    train_states = pipe.states[:int(len(pipe.states)*0.8)]
    pipe.normalizer.fit(pipe.states)
    from netwatch.features.sequences import build_sequences
    X_train, Y_train = build_sequences(train_states, pipe.normalizer)
    from netwatch.config import N_FEATURES, WORLD_MODEL_TYPE
    from netwatch.models.trainer import WorldModelTrainer
    pipe.trainer = WorldModelTrainer(model_type=WORLD_MODEL_TYPE, n_features=N_FEATURES)
    pipe.trainer.fit(X_train, Y_train, val_fraction=0.1, batch_size=32, epochs=5)
    from netwatch.forecasting.attack_forecaster import AttackForecaster
    pipe.attack_forecaster = AttackForecaster(pipe.trainer.model, pipe.normalizer, pipe.stage_predictor, feature_columns=pipe.feature_columns)
    pipe.attack_forecaster.fit_risk_head(pipe.states)
    return pipe


def test_ensemble_scorer_basic(pipeline):
    """Test that ensemble scorer runs all 8 detectors and outputs valid consensus metrics."""
    scorer = EnsembleScorer(pipeline=pipeline)
    result = scorer.evaluate_traffic(states=pipeline.states, k_steps=5)

    assert result["status"] == "ok"
    assert "consensus" in result
    assert "detectors" in result
    assert len(result["detectors"]) == 8

    consensus = result["consensus"]
    assert 0.0 <= consensus["score"] <= 100.0
    assert consensus["threat_level"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "BENIGN")
    assert 0 <= consensus["agreement_count"] <= 8
    assert "summary" in consensus
    assert "recommendation" in consensus
    assert "radar_data" in result
    assert len(result["radar_data"]["labels"]) == 8


def test_ensemble_scorer_reconnaissance_detection(pipeline):
    """Test that an anomalous/reconnaissance traffic profile triggers detector votes and high consensus."""
    # Synthetic reconnaissance scan state (port sweep across 50 ports)
    recon_state = NetworkState(
        timestamp="2026-09-11T12:00:00Z",
        features={
            "syn_rate": 2.5,
            "ack_rate": 0.2,
            "rst_rate": 6.0,
            "syn_ack_ratio": 1.5,
            "port_entropy": 3.8,
            "unique_dst_ports": 50.0,
            "unique_dst_hosts": 15.0,
            "packets_per_second": 8.0,
            "connection_rate": 8.0,
            "bytes": 2500.0,
            "packets": 50.0,
            "ttl_mean": 64.0,
            "payload_mean": 0.0,
            "payload_max": 0.0,
            "tcp_window_mean": 1024.0,
        },
        label=1,
        stage="Reconnaissance"
    )

    scorer = EnsembleScorer(pipeline=pipeline)
    result = scorer.evaluate_traffic(states=[recon_state], k_steps=5)

    assert result["status"] == "ok"
    consensus = result["consensus"]

    # Should detect high or critical threat
    assert consensus["threat_level"] in ("CRITICAL", "HIGH", "MEDIUM")
    assert consensus["agreement_count"] >= 3
    assert consensus["primary_stage"] in ("Reconnaissance", "Discovery")
    assert consensus["recommendation"]["recommended_action"] in ("block_source", "restrict_path", "isolate_host")
