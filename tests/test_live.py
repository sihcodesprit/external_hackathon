"""Tests for the live TShark monitoring module.

Covers: config, health detection, interface discovery, EK/JSON parsing,
normalization, window aggregation, flow tracking, the LivePipeline ingestion
loop, LiveManager session control (with a fake sensor) and the dashboard's
/api/live/* endpoints.

These tests never require a live TShark process.
"""
import time
from datetime import datetime, timezone

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


# ── URL target resolution & validation ─────────────────────────
def test_url_parse_valid_custom_port():
    from netwatch.live.url_target import UrlTarget
    t = UrlTarget("https://api.example.com:8443/login?x=1")
    assert t.scheme == "https"
    assert t.hostname == "api.example.com"
    assert t.port == 8443
    assert t.path == "/login"


def test_url_parse_default_ports():
    from netwatch.live.url_target import UrlTarget
    assert UrlTarget("https://example.com").port == 443
    assert UrlTarget("http://example.com").port == 80
    assert UrlTarget("https://example.com").protocol == "HTTPS"


def test_url_rejects_unsafe_schemes_and_hosts():
    from netwatch.live.url_target import UrlTarget
    for bad in ("javascript:alert(1)", "file:///etc/passwd", "data:text/html,x",
                "https://localhost", "http://127.0.0.1", "http://10.0.0.5",
                "ftp://example.com", "https://", "rm -rf /"):
        with pytest.raises(ValueError):
            UrlTarget(bad)


def test_url_private_hosts_allowed_when_configured():
    from netwatch.live.url_target import UrlTarget
    t = UrlTarget("http://10.0.0.5:8080", allow_private_hosts=True)
    assert t.hostname == "10.0.0.5"
    assert t.port == 8080


def test_resolve_hostname_mocked(monkeypatch):
    import socket

    from netwatch.live import url_target as ut

    def fake_getaddrinfo(host, port, family, socktype):
        if family == socket.AF_INET:
            return [(family, socktype, 6, "", ("93.184.216.34", 0)),
                    (family, socktype, 6, "", ("93.184.216.35", 0))]
        return [(family, socktype, 6, "", ("2606:2800:220:1:248:1893:25c8:1946", 0, 0, 0))]

    monkeypatch.setattr(ut.socket, "getaddrinfo", fake_getaddrinfo)
    ips = ut.resolve_hostname("example.com")
    assert "93.184.216.34" in ips
    assert "93.184.216.35" in ips
    assert any(":" in ip for ip in ips)


def test_build_bpf_filter():
    from netwatch.live.url_target import build_bpf_filter
    assert build_bpf_filter([], 443) == ""
    assert build_bpf_filter(["1.2.3.4"], 443) == "host 1.2.3.4 and port 443"
    multi = build_bpf_filter(["1.2.3.4", "5.6.7.8"], 8443)
    assert multi == "(host 1.2.3.4 or host 5.6.7.8) and port 8443"


def test_url_target_matches_and_direction():
    from netwatch.live.url_target import UrlTarget
    t = UrlTarget("https://example.com")
    t.current_ips = ["93.184.216.34"]
    outbound = {"src_ip": "192.168.1.10", "dst_ip": "93.184.216.34",
                "src_port": 50000, "dst_port": 443, "protocol": "TCP"}
    inbound = {"src_ip": "93.184.216.34", "dst_ip": "192.168.1.10",
               "src_port": 443, "dst_port": 50000, "protocol": "TCP"}
    unrelated = {"src_ip": "192.168.1.10", "dst_ip": "8.8.8.8",
                 "src_port": 50000, "dst_port": 443, "protocol": "TCP"}
    assert t.matches(outbound) is True
    assert t.matches(inbound) is True
    assert t.matches(unrelated) is False
    assert t.classify_direction(outbound) == "outbound"
    assert t.classify_direction(inbound) == "inbound"


# ── URL metrics ────────────────────────────────────────────────
def test_compute_url_metrics_real_events():
    from netwatch.live.url_monitor import compute_url_metrics
    from netwatch.live.url_target import UrlTarget

    t = UrlTarget("https://example.com")
    t.current_ips = ["93.184.216.34"]
    t.resolution_count = 2
    base = "2026-09-16T00:00:0"
    events = [
        {"src_ip": "192.168.1.10", "dst_ip": "93.184.216.34", "src_port": 50000,
         "dst_port": 443, "protocol": "TCP", "packet_length": 74, "tcp_flags": "S",
         "timestamp": base + "0Z"},
        {"src_ip": "93.184.216.34", "dst_ip": "192.168.1.10", "src_port": 443,
         "dst_port": 50000, "protocol": "TCP", "packet_length": 74, "tcp_flags": "SA",
         "timestamp": base + "1Z"},
        {"src_ip": "192.168.1.10", "dst_ip": "93.184.216.34", "src_port": 50000,
         "dst_port": 443, "protocol": "TCP", "packet_length": 300, "tcp_flags": "PA",
         "timestamp": base + "2Z", "tls_handshake_type": 1, "tls_server_name": "example.com"},
        {"src_ip": "93.184.216.34", "dst_ip": "192.168.1.10", "src_port": 443,
         "dst_port": 50000, "protocol": "TCP", "packet_length": 1200, "tcp_flags": "A",
         "timestamp": base + "3Z", "tcp_retransmission": True},
    ]
    m = compute_url_metrics(events, t, window_seconds=4)
    assert m["packets"] == 4
    assert m["bytes"] == 74 + 74 + 300 + 1200
    assert m["outbound_packets"] == 2
    assert m["inbound_packets"] == 2
    assert m["syn_count"] == 1
    assert m["syn_ack_count"] == 1
    assert m["tls_connection_count"] == 1
    assert m["retransmissions"] == 1
    assert m["destination_ip_count"] == 1
    assert m["dns_resolution_count"] == 2
    assert m["upload_rate"] > 0 and m["download_rate"] > 0
    feats = m["features"]
    assert feats["target_packet_count"] == 4
    assert feats["outbound_packet_count"] == 2
    assert feats["TLS_connection_count"] == 1
    assert "target_packet_size_entropy" in feats


# ── LivePipeline in URL mode ───────────────────────────────────
def test_live_pipeline_url_mode_filters_target_traffic():
    from netwatch.live.live_pipeline import LivePipeline
    from netwatch.live.live_state import LiveAnalysisState, LiveStatus
    from netwatch.live.url_target import UrlTarget

    target = UrlTarget("https://example.com")
    target.current_ips = ["10.0.0.5"]

    state = LiveAnalysisState(interface="eth0", window_size=30, step_size=5)
    state.mode = "live_url"
    state.status = LiveStatus.CAPTURING
    state.started_at = "2026-09-16T00:00:00"
    pipe = LivePipeline(state, target=target)

    epoch = time.time()
    ts = datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")
    matching = _raw_ek_packet()
    matching["timestamp"] = ts
    matching["layers"]["frame"]["frame.time_epoch"] = str(epoch)
    non_matching = _raw_ek_packet(**{"ip.ip.dst": "10.0.0.99"})
    non_matching["timestamp"] = ts
    non_matching["layers"]["frame"]["frame.time_epoch"] = str(epoch)

    for _ in range(3):
        pipe.process_event(matching)
    pipe.process_event(non_matching)

    assert state.events_received == 4
    assert state.packets == 3
    assert state.url_packets == 3
    assert state.url_flows == 1

    pipe.force_window()
    assert state.states_count == 1
    feats = state.network_state.get("features", {})
    assert "target_packet_count" in feats
    assert state.url_metrics_last.get("packets") == 3
    assert any(e["type"] == "flow" for e in state.timeline)


# ── LiveManager URL session ────────────────────────────────────
def test_manager_start_url_with_fake(live_manager_with_fake, monkeypatch):
    from netwatch.live import url_target as ut
    from netwatch.live.live_state import LiveStatus

    monkeypatch.setattr(ut, "resolve_hostname", lambda host: ["93.184.216.34"])
    mgr, fake = live_manager_with_fake

    result = mgr.start_url("https://example.com", "eth0")
    assert result["mode"] == "live_url"
    assert result["hostname"] == "example.com"
    assert result["analysis_id"]
    assert fake.started is True
    assert mgr.state.target["resolved_ips"] == ["93.184.216.34"]

    # URL-target traffic is observed; unrelated traffic is ignored.
    matching = _raw_ek_packet(**{"ip.ip.dst": "93.184.216.34"})
    epoch = time.time()
    matching["timestamp"] = datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")
    matching["layers"]["frame"]["frame.time_epoch"] = str(epoch)
    fake.feed(matching)
    fake.feed(_raw_ek_packet(**{"ip.ip.dst": "8.8.8.8"}))
    assert mgr.state.packets == 1
    assert mgr.state.status != LiveStatus.ERROR

    stop_res = mgr.stop()
    assert stop_res["status"] == "stopped"
    assert stop_res["mode"] == "live_url"


def test_manager_start_url_invalid_returns_error(live_manager_with_fake):
    mgr, _ = live_manager_with_fake
    res = mgr.start_url("file:///etc/passwd", "eth0")
    assert "error" in res


def test_manager_start_url_unresolvable(monkeypatch, live_manager_with_fake):
    from netwatch.live import url_target as ut
    monkeypatch.setattr(ut, "resolve_hostname", lambda host: [])
    mgr, _ = live_manager_with_fake
    res = mgr.start_url("https://nonexistent.invalid", "eth0")
    assert "error" in res


# ── URL Monitor API ────────────────────────────────────────────
def test_api_live_url_start_requires_url(client, live_manager_with_fake):
    resp = client.post("/api/live/url/start", json={"interface": "eth0"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_api_live_url_start_rejects_unsafe(client, live_manager_with_fake):
    resp = client.post("/api/live/url/start",
                       json={"url": "javascript:alert(1)", "interface": "eth0"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_api_live_url_start_status_stop(client, live_manager_with_fake, monkeypatch):
    from netwatch.live import url_target as ut
    monkeypatch.setattr(ut, "resolve_hostname", lambda host: ["93.184.216.34"])
    mgr, fake = live_manager_with_fake

    start = client.post("/api/live/url/start",
                        json={"url": "https://example.com", "interface": "eth0"})
    assert start.status_code == 200
    body = start.get_json()
    aid = body["analysis_id"]
    assert body["mode"] == "live_url"
    assert body["hostname"] == "example.com"

    status = client.get(f"/api/live/url/status/{aid}")
    assert status.status_code == 200
    st = status.get_json()
    assert st["mode"] == "live_url"
    assert st["target"]["hostname"] == "example.com"
    assert "traffic" in st and "risk" in st

    missing = client.get("/api/live/url/status/does-not-exist")
    assert missing.status_code == 404

    stop = client.post("/api/live/url/stop", json={"analysis_id": aid})
    assert stop.status_code == 200
    assert stop.get_json()["status"] == "stopped"
