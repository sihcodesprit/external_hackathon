"""Live analysis state — holds all metrics, status, and historical analysis data."""

import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional


class LiveStatus:
    STOPPED = "stopped"
    STARTING = "starting"
    CAPTURING = "capturing"
    WARMING_UP = "warming_up"
    ANALYZING = "analyzing"
    READY = "ready"
    ERROR = "error"
    STOPPING = "stopping"


class LiveAnalysisState:
    """Holds the complete state of a live analysis session."""

    def __init__(self, analysis_id: Optional[str] = None,
                 interface: str = "",
                 window_size: int = 30,
                 step_size: int = 5,
                 forecast_horizon: int = 5):
        self.analysis_id = analysis_id or uuid.uuid4().hex[:12]
        self.interface = interface
        self.status = LiveStatus.STOPPED
        self.mode = "live"
        self.sensor = "tshark"
        self.window_size = window_size
        self.step_size = step_size
        self.forecast_horizon = forecast_horizon
        self.started_at: Optional[str] = None
        self.stopped_at: Optional[str] = None

        # Telemetry
        self.packets = 0
        self.bytes_total = 0
        self.flows = 0
        self.hosts = 0
        self.packets_per_second = 0.0
        self.bytes_per_second = 0.0
        self.events_received = 0
        self.events_processed = 0
        self.events_dropped = 0

        # Model state
        self.world_model_status = "not_ready"
        self.states_count = 0

        # Rolling metrics for charts (last N seconds)
        self._pps_history: deque = deque(maxlen=300)
        self._bps_history: deque = deque(maxlen=300)
        self._flow_history: deque = deque(maxlen=300)
        self._host_history: deque = deque(maxlen=300)
        self._risk_history: deque = deque(maxlen=300)
        self._entropy_history: deque = deque(maxlen=300)

        # Latest analysis results
        self.network_state = {}
        self.forecast = {}
        self.risk = {}
        self.stage = {}
        self.graph = {}
        self.mitre = []
        self.explainability = {}
        self.counterfactual = {}
        self.ensemble = {}

        # Event log (bounded)
        self.event_log: deque = deque(maxlen=200)

        # Live document (canonical analysis format)
        self._doc: Optional[Dict] = None

    def update_telemetry(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
        now = time.time()
        self._pps_history.append((now, self.packets_per_second))
        self._bps_history.append((now, self.bytes_per_second))
        self._flow_history.append((now, self.flows))
        self._host_history.append((now, self.hosts))
        if self.risk:
            r = self.risk.get("current_risk", 0)
            self._risk_history.append((now, r))

    def log_event(self, event_type: str, message: str, data: Optional[dict] = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "message": message,
        }
        if data:
            entry["data"] = data
        self.event_log.appendleft(entry)

    def get_metrics_history(self) -> dict:
        return {
            "packets_per_second": [(t, v) for t, v in self._pps_history],
            "bytes_per_second": [(t, v) for t, v in self._bps_history],
            "flows": [(t, v) for t, v in self._flow_history],
            "hosts": [(t, v) for t, v in self._host_history],
            "risk": [(t, v) for t, v in self._risk_history],
        }

    def to_status_dict(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "status": self.status,
            "interface": self.interface,
            "sensor": self.sensor,
            "mode": self.mode,
            "packets": self.packets,
            "flows": self.flows,
            "hosts": self.hosts,
            "packets_per_second": round(self.packets_per_second, 1),
            "bytes_per_second": round(self.bytes_per_second, 1),
            "events_received": self.events_received,
            "events_processed": self.events_processed,
            "events_dropped": self.events_dropped,
            "states_count": self.states_count,
            "world_model_status": self.world_model_status,
            "window_size": self.window_size,
            "step_size": self.step_size,
            "forecast_horizon": self.forecast_horizon,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "current_risk": self.risk.get("current_risk", 0) if self.risk else 0,
            "current_stage": self.stage.get("predicted_stage", "Unknown") if self.stage else "Unknown",
            "last_event": self.event_log[0] if self.event_log else None,
        }

    def to_analysis_dict(self) -> dict:
        """Return the canonical analysis document shape (matches build_document_from_pipeline)."""
        forecast_data = {
            "status": "ok",
            "k": self.forecast_horizon,
            "current": self.forecast.get("current", {
                "risk": 0, "stage": "Unknown", "confidence": 0,
                "features": {}, "explanation": {"summary": "Collecting data.", "top_features": []}
            }),
            "future": self.forecast.get("future", []),
            "temporal_explanation": self.forecast.get("temporal_explanation", {}),
        }
        return {
            "status": "ok",
            "type": "live_traffic",
            "analysis_id": self.analysis_id,
            "filename": f"live_{self.interface}",
            "member": None,
            "source": "LIVE CAPTURE (TShark)",
            "occurrence": None,
            "n_records": self.packets,
            "n_states": self.states_count,
            "traffic_summary": {
                "n_packets": self.packets,
                "n_bytes": self.bytes_total,
                "n_flows": self.flows,
                "n_hosts": self.hosts,
                "duration_seconds": round(time.time() - (datetime.fromisoformat(
                    self.started_at).timestamp() if self.started_at else time.time()), 1),
            },
            "network_state": None,
            "forecast": forecast_data,
            "graph": self.graph,
            "counterfactual": self.counterfactual,
            "mitre_trajectory": self.mitre,
            "ensemble": self.ensemble,
            "topology": {},
            "entities": {},
            "state_groups": [],
            "data_info": {
                "n_records": self.packets,
                "n_states": self.states_count,
                "mode": "live",
            },
            "started_at": self.started_at,
            "finished_at": self.stopped_at or datetime.now().isoformat(),
            "live": {
                "interface": self.interface,
                "world_model_status": self.world_model_status,
                "events_received": self.events_received,
                "events_dropped": self.events_dropped,
            },
        }