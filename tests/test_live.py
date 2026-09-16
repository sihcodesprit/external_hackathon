"""Tests for the live TShark monitoring module.

Covers: config, health detection, interface discovery, EK/JSON parsing,
normalization, window aggregation, flow tracking, the LivePipeline ingestion
loop, LiveManager session control (with a fake sensor) and the dashboard's
/api/live/* endpoints.

These tests never require a live TShark process.
"""
from datetime import datetime, timezone
import time

import pytest


# ── Test fixtures ──────────────────────────────────────────────
def _raw_ek_packet(**overrides) -> dict:
    """A realistic TShark `-T ek` data document (one JSON object per line)."""
    layer = {
        "frame": {
            "frame.time_epoch": "1726000000.123456789",
            "frame.len": "84",
            "frame.protocols": "eth:ethertype:ip:tcp",
        },
        "ip": {
            "ip.src": "192.168.1.10",
            "ip.dst": "10.0.0.5",
            "ip.proto": "6",
            "ip.ttl": "64",
        },
        "tcp": {
            "tcp.srcport": "12345",
            "tcp.dstport": "443",
            "tcp.flags": "0x018",
            "tcp.flags.str": "SA",
            "tcp.window_size_value": "64240",
        },
    }
    if "tcp.flags" in overrides:
        layer["tcp"]["tcp.flags"] = overrides.pop("tcp.flags")
        layer["tcp"]["tcp.flags.str"] = overrides.pop("tcp.flags.str", "SA")
    doc = {"timestamp": "2024-09-06T12:26:40.123456789Z", "layers": layer}
    for k, v in overrides.items():
        parts = k.split(".")
        seg = layer
        if parts[0] == "frame":
            seg = layer["frame"]
        elif parts[0] == "ip":
            seg = layer["ip"]
        elif parts[0] == "tcp":
            seg = layer["tcp"]
        seg[".".join(parts[1:])] = v
    return doc


def _raw_ek_index() -> dict:
    return {"index": {"_index": "packets-2026-09-16", "_type": "_doc", "_score": None}}


class FakeSensor:
    """Stand-in for TSharkSensor that never touches a subprocess."""

    def __init__(self):
        self.started = False
        self._stats = {"error": None, "packets_captured": 0}
        self._callback = None

    def start(self, interface, callback=None, bpf_filter=None, output_format=None):
        self.started = True
        self._callback = callback
        self._stats = {"error": None, "packets_captured": 0}
        return True

    def feed(self, event: dict):
        if self._callback:
            self._callback(event)

    def stop(self):
        self.started = False
        return dict(self._stats)

    def check_alive(self):
        return None

    @property
    def stats(self):
        return dict(self._stats)


@pytest.fixture()
def live_manager_with_fake(monkeypatch):
    from netwatch.live.manager import LiveManager
    mgr = LiveManager()
    fake = FakeSensor()
    monkeypatch.setattr(mgr, "_sensor", fake)
    monkeypatch.setattr(mgr, "subscribe", lambda cb: None)
    monkeypatch.setattr(mgr, "unsubscribe", lambda cb: None)
    yield mgr, fake
    mgr._running = False


# ── Health & discovery ─────────────────────────────────────────
def test_find_tshark_returns_expected_shape():
    from netwatch.live.health import find_tshark
    info = find_tshark("tshark-definitely-not-present-binary")
    assert set(info) >= {"installed", "path", "version", "platform", "capture_available"}


def test_detect_tshark_flat_shape():
    from netwatch.live.health import detect_tshark
    info = detect_tshark("tshark-definitely-not-present-binary")
    assert "available" in info
    assert "path" in info and "version" in info and "error" in info
    assert info["available"] is False
    assert "tshark" in (info["error"] or "").lower()


def test_discover_interfaces_returns_list():
    from netwatch.live.interface import discover_interfaces
    ifaces = discover_interfaces()
    assert isinstance(ifaces, list)
    for i in ifaces:
        assert "name" in i
        assert "is_loopback" in i or "state" in i


def test_validate_interface_allowlist():
    from netwatch.live.tshark_sensor import _validate_interface
    assert _validate_interface("eth0") == "eth0"
    assert _validate_interface("wlan0.1") == "wlan0.1"
    with pytest.raises(ValueError):
        _validate_interface("eth0; rm -rf /")
    with pytest.raises(ValueError):
        _validate_interface("")
    with pytest.raises(ValueError):
        _validate_interface("x" * 300)


# ── Parsing & normalization ────────────────────────────────────
def test_parse_ek_line_realistic():
    from netwatch.live.event_parser import parse_ek_line
    pk = parse_ek_line(_raw_ek_packet())
    assert pk is not None
    assert pk["src_ip"] == "192.168.1.10"
    assert pk["dst_ip"] == "10.0.0.5"
    assert pk["src_port"] == 12345
    assert pk["dst_port"] == 443
    assert pk["protocol"] == "TCP"
    assert pk["packet_length"] == 84
    assert pk["tcp_flags"] == "SA"
    assert pk["timestamp"].endswith("Z")


def test_parse_ek_line_index_frame_ignored():
    from netwatch.live.event_parser import parse_ek_line
    assert parse_ek_line(_raw_ek_index()) is None
    assert parse_ek_line({}) is None


def test_parse_ek_line_no_ip_returns_none():
    from netwatch.live.event_parser import parse_ek_line
    doc = _raw_ek_packet()
    doc["layers"]["ip"] = {"ip.proto": "6"}
    assert parse_ek_line(doc) is None


def test_parse_json_array_line():
    import json
    from netwatch.live.event_parser import parse_json_array_line
    doc = _raw_ek_packet()
    assert parse_json_array_line("," + json.dumps(doc)) is not None
    assert parse_json_array_line("[") is None


def test_event_to_packet_record():
    from netwatch.live.event_parser import parse_ek_line
    from netwatch.live.normalizer import event_to_packet_record
    pk = parse_ek_line(_raw_ek_packet())
    pr = event_to_packet_record(pk)
    assert pr is not None
    assert pr.src_ip == "192.168.1.10"
    assert pr.dst_port == 443
    assert pr.protocol == "TCP"
    assert pr.bytes_sent == 84
    assert pr.payload_size == 44
    assert event_to_packet_record({}) is None


# ── Window manager & flow tracker ─────────────────────────────
def test_window_manager_stats(monkeypatch):
    from netwatch.live.window_manager import WindowManager

    now = [1_000_000.0]

    def fake_time():
        return now[0]

    monkeypatch.setattr("netwatch.live.window_manager.time.time", fake_time)
    wm = WindowManager(window_size=30, step_size=5)
    ev = _raw_ek_packet()
    for _ in range(10):
        wm.add_event(ev)
    assert wm.stats["events_received"] == 10
    assert wm.stats["events_buffered"] == 10
    # No step elapsed yet
    assert wm.check_step() is None
    now[0] += 6
    window = wm.check_step()
    assert window is not None
    assert len(window) == 10


def test_flow_tracker_counts():
    from netwatch.live.event_parser import parse_ek_line
    from netwatch.live.flow_tracker import FlowTracker

    tracker = FlowTracker()
    for _ in range(5):
        tracker.process_event(parse_ek_line(_raw_ek_packet()))
    # Different 5-tuple force a new flow
    other = _raw_ek_packet(**{"ip.ip.dst": "10.0.0.99"})
    tracker.process_event(parse_ek_line(other))
    stats = tracker.get_stats()
    assert stats["total_flows"] == 2
    assert stats["hosts_seen"] == 3
    flows = tracker.get_current_flows()
    tcp_flow = next(f for f in flows if f["dst_ip"] == "10.0.0.5")
    assert tcp_flow["packet_count"] == 5
    # "SA" is a SYN-ACK; flow counts it under syn_ack_count, not syn_count
    assert tcp_flow["syn_ack_count"] == 5
    assert tcp_flow["syn_count"] == 0


# ── LivePipeline ingestion loop ────────────────────────────────
def test_live_pipeline_ingests_ek_events():
    from netwatch.live.live_pipeline import LivePipeline
    from netwatch.live.live_state import LiveAnalysisState, LiveStatus

    state = LiveAnalysisState(interface="eth0", window_size=30, step_size=5)
    state.status = LiveStatus.CAPTURING
    state.started_at = "2026-09-16T00:00:00"
    pipe = LivePipeline(state)

    doc = _raw_ek_packet()
    # Events must fall within the active window relative to wall-clock now
    epoch = time.time()
    ts = datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")
    doc["timestamp"] = ts
    doc["layers"]["frame"]["frame.time_epoch"] = str(epoch)
    for _ in range(4):
        pipe.process_event(doc)
    # Interleaved EK control frame is skipped cleanly
    pipe.process_event(_raw_ek_index())

    assert state.events_received == 5
    assert state.packets == 4
    assert state.bytes_total == 4 * 84
    assert pipe.window_mgr.stats["events_buffered"] == 4
    assert pipe.flow_tracker.get_stats()["total_flows"] == 1

    # Force the buffered window through NetworkState construction
    pipe.force_window()
    assert state.states_count == 1
    assert state.network_state.get("features")
    assert state.status in (LiveStatus.ANALYZING, LiveStatus.CAPTURING)
    assert pipe.doc is not None
    assert pipe.doc["source"] == "LIVE CAPTURE (TShark)"
    assert pipe.doc["n_records"] == 4


def test_live_pipeline_check_window_no_step_returns_none():
    from netwatch.live.live_pipeline import LivePipeline
    from netwatch.live.live_state import LiveAnalysisState

    pipe = LivePipeline(LiveAnalysisState(interface="eth0", window_size=30, step_size=5))
    assert pipe.check_window() is None


# ── LiveManager session control ───────────────────────────────
def test_manager_start_stop(live_manager_with_fake):
    from netwatch.live.manager import LiveManager
    from netwatch.live.live_state import LiveStatus

    mgr, fake = live_manager_with_fake
    assert mgr.is_active is False

    result = mgr.start("eth0", window_size=30, step_size=5, forecast_horizon=5)
    assert result["status"] in ("starting", "capturing")
    assert result["analysis_id"]
    assert fake.started is True
    assert mgr.is_active is True

    # Feed a live packet through the callback chain
    fake.feed(_raw_ek_packet())
    assert mgr.state.packets == 1
    assert mgr.state.status != LiveStatus.ERROR

    stop_res = mgr.stop()
    assert stop_res["status"] == "stopped"
    assert stop_res["analysis_id"] == result["analysis_id"]
    assert mgr.state.status == LiveStatus.STOPPED
    assert len(mgr.get_history()) >= 1


def test_manager_disabled(monkeypatch):
    from netwatch.live import manager as manager_module
    from netwatch.live.manager import LiveManager

    monkeypatch.setattr(manager_module, "LIVE_ENABLED", False)
    mgr = LiveManager()
    res = mgr.start("eth0")
    assert "error" in res


# ── Dashboard API ─────────────────────────────────────────────
@pytest.fixture()
def client():
    from netwatch.dashboard.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_api_live_health(client):
    resp = client.get("/api/live/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "available" in data
    assert "error" in data


def test_api_live_interfaces(client):
    resp = client.get("/api/live/interfaces")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "interfaces" in data
    assert isinstance(data["interfaces"], list)


def test_api_live_status_idle(client):
    resp = client.get("/api/live/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("active") is False


def test_api_live_start_stop(client, live_manager_with_fake):
    # LiveManager is a singleton; the route resolves the same instance we patched.
    mgr, fake = live_manager_with_fake

    start = client.post("/api/live/start", json={"interface": "eth0"})
    assert start.status_code == 200
    assert "analysis_id" in start.get_json()
    assert fake.started is True

    status = client.get("/api/live/status")
    assert status.get_json()["active"] is True
    assert status.get_json()["interface"] == "eth0"

    stop = client.post("/api/live/stop")
    assert stop.get_json()["status"] == "stopped"


def test_api_live_events_requires_session(client):
    resp = client.get("/api/live/events")
    assert resp.status_code == 404