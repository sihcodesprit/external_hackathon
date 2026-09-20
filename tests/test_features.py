"""Unit tests for feature extraction and NetworkState construction."""

from datetime import UTC, datetime, timedelta

import pytest

from netwatch.config import get_feature_columns
from netwatch.features.entropy_features import shannon_entropy
from netwatch.features.network_state import (
    NetworkState,
    StateBuilder,
    compute_window_features,
)
from netwatch.ingestion.parser import PacketRecord


def _ts(base, sec):
    return (base + timedelta(seconds=sec)).isoformat().replace("+00:00", "Z")


def test_port_entropy_uniform():
    assert shannon_entropy([]) == 0.0
    assert shannon_entropy([80, 80]) == 0.0
    assert shannon_entropy([80, 443, 22, 53]) == pytest.approx(2.0, abs=1e-2)


def _record(ts, src="1.1.1.1", dst="2.2.2.2", dport=80, flags="A",
            payload=100, ttl=64, window=65535):
    return PacketRecord(timestamp=ts, src_ip=src, dst_ip=dst, dst_port=dport,
                        flags=flags, payload_size=payload, ttl=ttl,
                        tcp_window=window, bytes_sent=payload, label=0)


def test_compute_window_features_shape():
    base = datetime.now(UTC)
    pkts = [_record(_ts(base, i)) for i in range(60)]
    feats = compute_window_features(pkts)
    # basic features from compute_window_features
    expected_basic = {
        "bytes", "packets", "ttl_mean", "payload_mean", "payload_max",
        "tcp_window_mean", "packets_per_second", "connection_rate",
        "unique_dst_ports", "unique_dst_hosts", "syn_rate", "ack_rate",
        "rst_rate", "syn_ack_ratio", "port_entropy"
    }
    for col in expected_basic:
        assert col in feats, col
    assert feats["packets"] == 60
    assert feats["ttl_mean"] == 64.0
    # ACK-only traffic -> zero SYN rate
    assert feats["syn_rate"] == 0.0


def test_compute_window_features_flags_and_ports():
    base = datetime.now(UTC)
    pkts = []
    for i, (flags, dport) in enumerate([("S", 22), ("S", 23), ("S", 80),
                                        ("SA", 443), ("R", 22)]):
        pkts.append(_record(_ts(base, i), dport=dport, flags=flags,
                            payload=0, ttl=60))
    feats = compute_window_features(pkts)
    assert feats["unique_dst_ports"] == 4
    assert feats["syn_rate"] > 0
    assert feats["rst_rate"] > 0
    assert feats["port_entropy"] > 0


def test_state_builder_creates_ordered_states():
    base = datetime.now(UTC)
    pkts = [_record(_ts(base, i * 1.0), dport=(80 if i % 2 else 443))
            for i in range(200)]  # ~200s of traffic
    states = StateBuilder(window_seconds=30, window_step=10,
                          group_by_pair=False).build_states(pkts)
    assert len(states) > 1
    assert isinstance(states[0], NetworkState)
    ts = [s.timestamp for s in states]
    assert ts == sorted(ts)  # time-ordered
    # window labels derived from traffic (all benign here)
    assert all(s.label == 0 for s in states)


def test_state_vector_uses_feature_columns():
    base = datetime.now(UTC)
    states = StateBuilder(window_seconds=30, window_step=10,
                          group_by_pair=False).build_states(
        [_record(_ts(base, i)) for i in range(60)])
    vec = states[0].vector()
    assert len(vec) == len(get_feature_columns())


def test_state_builder_groups_by_pair():
    base = datetime.now(UTC)
    pkts = [_record(_ts(base, i), src="1.1.1.1", dst="2.2.2.2") for i in range(50)]
    pkts += [_record(_ts(base, i), src="3.3.3.3", dst="4.4.4.4") for i in range(50)]
    states = StateBuilder(window_seconds=30, window_step=10,
                          group_by_pair=True).build_states(pkts)
    assert len(states) >= 2
    pairs = {(s.src_ip, s.dst_ip) for s in states}
    assert ("1.1.1.1", "2.2.2.2") in pairs
    assert ("3.3.3.3", "4.4.4.4") in pairs
