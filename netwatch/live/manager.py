"""Global live analysis manager — singleton controlling live sessions."""

import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Callable, List, Optional

from netwatch.live.config import (
    LIVE_DASHBOARD_UPDATE_INTERVAL,
    LIVE_ENABLED,
    LIVE_URL_DNS_REFRESH_SECONDS,
)
from netwatch.live.live_pipeline import LivePipeline
from netwatch.live.live_state import LiveAnalysisState, LiveStatus
from netwatch.live.tshark_sensor import TSharkSensor
from netwatch.live.url_target import UrlTarget, build_bpf_filter

logger = logging.getLogger(__name__)


class LiveManager:
    """Manages live analysis sessions with background processing."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._sensor = TSharkSensor()
        self._pipeline: Optional[LivePipeline] = None
        self._state: Optional[LiveAnalysisState] = None
        self._url_target: Optional[UrlTarget] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._dashboard_thread: Optional[threading.Thread] = None
        self._dns_thread: Optional[threading.Thread] = None
        self._dns_stop = threading.Event()
        self._last_result_version = -1
        self._running = False
        self._subscribers: List[Callable] = []
        self._subscribers_lock = threading.Lock()
        self._history: List[dict] = []

    @property
    def is_active(self) -> bool:
        return self._running and self._state is not None and self._state.status != LiveStatus.STOPPED

    @property
    def state(self) -> Optional[LiveAnalysisState]:
        return self._state

    @property
    def pipeline(self) -> Optional[LivePipeline]:
        return self._pipeline

    def subscribe(self, callback: Callable):
        with self._subscribers_lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        with self._subscribers_lock:
            self._subscribers = [cb for cb in self._subscribers if cb is not callback]

    def _notify(self, event_type: str, data: dict):
        with self._subscribers_lock:
            callbacks = list(self._subscribers)
        for cb in callbacks:
            try:
                cb(event_type, data)
            except Exception:
                pass

    def start(self, interface: str, window_size: int = 30,
              step_size: int = 5, forecast_horizon: int = 5) -> dict:
        """Start a live analysis session."""
        if not LIVE_ENABLED:
            return {"error": "Live monitoring is disabled (NETWATCH_LIVE_ENABLED=false)"}
        if self._running:
            self.stop()

        self._url_target = None
        analysis_id = uuid.uuid4().hex[:12]
        self._state = LiveAnalysisState(
            analysis_id=analysis_id,
            interface=interface,
            window_size=window_size,
            step_size=step_size,
            forecast_horizon=forecast_horizon,
        )
        self._pipeline = LivePipeline(self._state)
        self._state.status = LiveStatus.STARTING
        self._state.started_at = datetime.now().isoformat()

        def event_callback(event: dict):
            if self._pipeline and self._running:
                self._pipeline.process_event(event)

        started = self._sensor.start(interface, callback=event_callback)
        if not started:
            err = self._sensor.stats.get("error", "Unknown error")
            self._state.status = LiveStatus.ERROR
            self._state.log_event("error", f"TShark failed to start: {err}")
            return {
                "analysis_id": analysis_id,
                "status": "error",
                "error": err,
            }

        self._running = True
        self._state.status = LiveStatus.CAPTURING
        self._state.log_event("capture", f"TShark started on {interface}")

        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="live-worker",
            daemon=True,
        )
        self._worker_thread.start()

        self._dashboard_thread = threading.Thread(
            target=self._dashboard_loop,
            name="live-dashboard",
            daemon=True,
        )
        self._dashboard_thread.start()

        return {
            "analysis_id": analysis_id,
            "status": "starting",
            "mode": "live",
            "interface": interface,
            "sensor": "tshark",
        }

    def start_url(self, url: str, interface: str, window_size: int = 30,
                  step_size: int = 5, forecast_horizon: int = 5,
                  allow_private_hosts: bool = False) -> dict:
        """Start a live URL-target monitoring session.

        The URL is resolved to a destination IP set and TShark is started with
        a filter for that destination. The URL is never fetched — only the
        local network transmission involving the resolved endpoints is observed.
        """
        if not LIVE_ENABLED:
            return {"error": "Live monitoring is disabled (NETWATCH_LIVE_ENABLED=false)"}
        if not interface:
            return {"error": "Interface is required"}

        try:
            target = UrlTarget(url, allow_private_hosts=allow_private_hosts)
        except ValueError as e:
            return {"error": str(e)}

        if self._running:
            self.stop()

        resolved = target.resolve()
        if not resolved:
            return {"error": f"Could not resolve hostname '{target.hostname}'. "
                             "Check the URL or DNS connectivity."}

        analysis_id = uuid.uuid4().hex[:12]
        self._state = LiveAnalysisState(
            analysis_id=analysis_id,
            interface=interface,
            window_size=window_size,
            step_size=step_size,
            forecast_horizon=forecast_horizon,
        )
        self._state.mode = "live_url"
        self._state.source = {"type": "url", "url": target.url, "interface": interface}
        self._state.target = target.to_dict()
        self._state.url_resolutions = target.resolution_count
        self._url_target = target
        self._pipeline = LivePipeline(self._state, target=target)
        self._state.status = LiveStatus.STARTING
        self._state.started_at = datetime.now().isoformat()
        self._state.append_timeline(
            "dns", f"DNS resolution observed ({len(resolved)} IP{'s' if len(resolved) != 1 else ''})",
            {"hostname": target.hostname, "ips": list(resolved)},
        )
        self._state.log_event("dns",
                              f"Resolved {target.hostname} -> {', '.join(resolved)}")

        def event_callback(event: dict):
            if self._pipeline and self._running:
                self._pipeline.process_event(event)

        bpf = build_bpf_filter(resolved, target.port)
        started = self._sensor.start(interface, callback=event_callback,
                                     bpf_filter=bpf or None)
        if not started:
            err = self._sensor.stats.get("error", "Unknown error")
            self._state.status = LiveStatus.ERROR
            self._state.log_event("error", f"TShark failed to start: {err}")
            return {"analysis_id": analysis_id, "status": "error", "error": err}

        self._running = True
        self._state.status = LiveStatus.CAPTURING
        self._state.log_event("capture",
                              f"TShark started on {interface} monitoring {target.hostname}:{target.port}")

        self._worker_thread = threading.Thread(
            target=self._worker_loop, name="live-worker", daemon=True)
        self._worker_thread.start()
        self._dashboard_thread = threading.Thread(
            target=self._dashboard_loop, name="live-dashboard", daemon=True)
        self._dashboard_thread.start()

        self._dns_stop = threading.Event()
        self._dns_thread = threading.Thread(
            target=self._dns_loop, name="live-dns", daemon=True)
        self._dns_thread.start()

        return {
            "analysis_id": analysis_id,
            "mode": "live_url",
            "status": "starting",
            "url": target.url,
            "hostname": target.hostname,
            "interface": interface,
            "sensor": "tshark",
            "target": target.to_dict(),
        }

    def _dns_loop(self):
        """Periodically refresh the target IP set without interrupting capture."""
        while self._running and self._url_target is not None:
            if self._dns_stop.wait(max(LIVE_URL_DNS_REFRESH_SECONDS, 5)):
                break
            if not self._running or self._url_target is None:
                break
            try:
                target = self._url_target
                previous = set(target.current_ips)
                new = target.resolve()
                if self._state is None:
                    continue
                self._state.url_resolutions = target.resolution_count
                self._state.target = target.to_dict()
                if set(new) != previous and new:
                    self._state.url_target_ip_changes += 1
                    self._state.append_timeline(
                        "dns",
                        f"TARGET IPs UPDATED: {len(previous)} -> {len(new)}",
                        {"previous": sorted(previous), "current": sorted(new)},
                    )
                    self._state.log_event(
                        "dns", f"Target IPs updated: {len(previous)} -> {len(new)}")
                else:
                    self._state.append_timeline(
                        "dns", f"DNS refresh: {len(new)} IPs (unchanged)")
            except Exception as e:  # noqa: BLE001
                logger.debug("DNS refresh failed: %s", e)

    def stop(self) -> dict:
        """Stop the current live analysis session."""
        self._running = False
        self._dns_stop.set()
        if self._state:
            self._state.status = LiveStatus.STOPPING

        sensor_stats = self._sensor.stop()

        if self._state:
            self._state.stopped_at = datetime.now().isoformat()
            self._state.status = LiveStatus.STOPPED
            self._state.log_event("capture", "TShark stopped")

            # Persist to history
            self._history.append({
                "analysis_id": self._state.analysis_id,
                "mode": self._state.mode,
                "url": (self._state.source or {}).get("url") if self._state.source else None,
                "interface": self._state.interface,
                "started_at": self._state.started_at,
                "stopped_at": self._state.stopped_at,
                "packets": self._state.packets,
                "flows": self._state.flows,
                "hosts": self._state.hosts,
                "states": self._state.states_count,
                "world_model_status": self._state.world_model_status,
            })

        self._url_target = None
        if self._dns_thread and self._dns_thread.is_alive() and self._dns_thread is not threading.current_thread():
            self._dns_thread.join(timeout=2)
        self._dns_thread = None

        result = {
            "status": "stopped",
            "sensor_stats": sensor_stats,
        }
        if self._state:
            result["analysis_id"] = self._state.analysis_id
            result["mode"] = self._state.mode
        return result

    def _worker_loop(self):
        """Background worker: process window steps."""
        while self._running:
            try:
                if self._pipeline:
                    self._pipeline.check_window()
            except Exception as e:
                logger.warning("Worker error: %s", e)
            # Check sensor health
            error = self._sensor.check_alive()
            if error and self._state:
                self._state.status = LiveStatus.ERROR
                self._state.log_event("error", error)
                self._running = False
                break
            time.sleep(0.5)

    def _dashboard_loop(self):
        """Background loop: publish dashboard updates at regular intervals."""
        while self._running:
            try:
                if self._state and self._pipeline:
                    self._pipeline._update_telemetry()
                    status = self._state.to_status_dict()
                    self._notify("update", status)
                    if self._state.mode == "live_url":
                        self._publish_url_events(status)
            except Exception as e:
                logger.debug("Dashboard update error: %s", e)
            time.sleep(LIVE_DASHBOARD_UPDATE_INTERVAL)

    def _publish_url_events(self, status: dict):
        """Publish URL-specific SSE channels from real observed state."""
        state = self._state
        metrics = state.url_metrics_last or {}
        self._notify("url_status", {
            "analysis_id": state.analysis_id,
            "status": state.status,
            "mode": state.mode,
            "target": state.target,
            "source": state.source,
            "traffic": {
                "packets": state.url_packets,
                "bytes": state.url_bytes,
                "flows": state.url_flows,
                "packets_per_second": metrics.get("packets_per_second", 0.0),
                "bytes_per_second": metrics.get("bytes_per_second", 0.0),
                "upload_rate": metrics.get("upload_rate", 0.0),
                "download_rate": metrics.get("download_rate", 0.0),
                "outbound_packets": state.url_outbound_packets,
                "outbound_bytes": state.url_outbound_bytes,
                "inbound_packets": state.url_inbound_packets,
                "inbound_bytes": state.url_inbound_bytes,
                "active_connections": metrics.get("flows", 0),
                "tls_connections": state.url_tls_connections,
                "retransmissions": state.url_retransmissions,
                "syn_count": state.url_syn_count,
                "rst_count": state.url_rst_count,
            },
            "url_metrics": metrics,
            "world_model_status": state.world_model_status,
        })
        # Timeline-derived channels: dns / connection / traffic / flow / ...
        for ev in state.consume_unpublished_timeline():
            self._notify(ev.get("type", "event"), ev)

        # Analysis result channels, only when a new window has been analysed.
        if state.states_count != self._last_result_version:
            self._last_result_version = state.states_count
            for name in ("network_state", "risk", "forecast", "stage", "graph",
                         "mitre", "explainability", "counterfactual"):
                value = getattr(state, name, None)
                if value:
                    self._notify(name, value if isinstance(value, dict) else {"value": value})

    def get_history(self) -> list:
        return list(reversed(self._history))

    def get_active_doc(self) -> Optional[dict]:
        if self._pipeline:
            return self._pipeline.doc
        return None
