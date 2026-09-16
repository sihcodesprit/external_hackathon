"""Global live analysis manager — singleton controlling live sessions."""

import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from netwatch.live.config import LIVE_DASHBOARD_UPDATE_INTERVAL, LIVE_ENABLED
from netwatch.live.live_pipeline import LivePipeline
from netwatch.live.live_state import LiveAnalysisState, LiveStatus
from netwatch.live.tshark_sensor import TSharkSensor

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
        self._worker_thread: Optional[threading.Thread] = None
        self._dashboard_thread: Optional[threading.Thread] = None
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

    def stop(self) -> dict:
        """Stop the current live analysis session."""
        self._running = False
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
                "interface": self._state.interface,
                "started_at": self._state.started_at,
                "stopped_at": self._state.stopped_at,
                "packets": self._state.packets,
                "flows": self._state.flows,
                "hosts": self._state.hosts,
                "states": self._state.states_count,
                "world_model_status": self._state.world_model_status,
            })

        result = {
            "status": "stopped",
            "sensor_stats": sensor_stats,
        }
        if self._state:
            result["analysis_id"] = self._state.analysis_id
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
                    self._notify("update", self._state.to_status_dict())
            except Exception as e:
                logger.debug("Dashboard update error: %s", e)
            time.sleep(LIVE_DASHBOARD_UPDATE_INTERVAL)

    def get_history(self) -> list:
        return list(reversed(self._history))

    def get_active_doc(self) -> Optional[dict]:
        if self._pipeline:
            return self._pipeline.doc
        return None
