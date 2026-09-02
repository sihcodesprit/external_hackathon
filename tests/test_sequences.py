"""Unit tests for temporal sequence construction and splits."""

import numpy as np
import pytest

from main.netwatch.features.network_state import NetworkState
from main.netwatch.features.sequences import (
    StateNormalizer,
    assign_labels_and_stages,
    build_seq_labels,
    build_sequences,
    split_by_group,
    temporal_split,
)
from main.netwatch.ingestion.synthetic import generate_trace


def _baseline_states(n=20):
    states = []
    for i in range(n):
        states.append(NetworkState(
            timestamp=f"2026-01-01T00:{i:02d}:00Z",
            features={"bytes": 100.0 + i, "packets": 5.0, "ttl_mean": 64.0,
                      "payload_mean": 200.0, "payload_max": 300.0,
                      "tcp_window_mean": 65535.0, "packets_per_second": 5.0,
                      "connection_rate": 5.0, "unique_dst_ports": 2.0,
                      "unique_dst_hosts": 1.0, "syn_rate": 0.1,
                      "ack_rate": 4.0, "rst_rate": 0.0,
                      "syn_ack_ratio": 0.1, "port_entropy": 1.0},
            label=0, stage="Benign"))
    return states


@pytest.fixture()
def norm_states():
    from main.netwatch.pipeline import Pipeline
    pipe = Pipeline()
    pipe.load_data(n_traces=2, seed=7, duration_minutes=60)
    return pipe.states


def test_normalizer_zero_variance_guard():
    flat = _baseline_states(5)
    norm = StateNormalizer()
    norm.fit(flat)
    assert len(norm.std) == len(norm.mean) > 0
    # constant column -> std falls back to 1.0
    assert all(s >= 1.0 for s in norm.std)


def test_temporal_split_no_shuffle(norm_states):
    train, val = temporal_split(norm_states, 0.2)
    assert len(train) + len(val) == len(norm_states)
    assert len(val) > 0
    # no state from val appears in train
    train_ts = {s.timestamp for s in train}
    assert all(s.timestamp not in train_ts for s in val)


def test_split_by_group():
    states = []
    for i, src in enumerate(["A", "A", "B", "B", "B"]):
        states.append(NetworkState(timestamp=f"2026-01-01T00:00:{i:02d}Z",
                                   features={}, src_ip=src))
    train, val = split_by_group(states, key_fn=lambda s: s.src_ip, val_key="B")
    assert {s.src_ip for s in val} == {"B"}
    assert all(s.src_ip == "A" for s in train)


def test_build_seq_labels_alignment(norm_states):
    norm = StateNormalizer(); norm.fit(norm_states)
    X, Y = build_sequences(norm_states, norm, sequence_length=8, horizon=1)
    labels = build_seq_labels(norm_states, sequence_length=8, horizon=1)
    assert len(X) == len(labels) == len(Y)
    # the label for row i is the label of S[i + 8]
    for i in range(3):
        expected = int(norm_states[i + 8].label or 0)
        assert labels[i] == expected


def test_stage_assignment_heuristic_fallback():
    states = [NetworkState(
        timestamp="2026-01-01T00:00:00Z",
        features={"bytes": 0.0, "packets": 0.0, "ttl_mean": 64.0,
                  "payload_mean": 900.0, "payload_max": 900.0,
                  "tcp_window_mean": 65535.0, "packets_per_second": 20.0,
                  "connection_rate": 20.0, "unique_dst_ports": 3.0,
                  "unique_dst_hosts": 2.0, "syn_rate": 3.0,
                  "ack_rate": 5.0, "rst_rate": 1.0,
                  "syn_ack_ratio": 0.6, "port_entropy": 1.2},
        label=None, stage=None)]
    assigned = assign_labels_and_stages(states, stage_vocab=None)
    assert assigned[0].label == 1  # anomalous profile
    assert assigned[0].stage is not None