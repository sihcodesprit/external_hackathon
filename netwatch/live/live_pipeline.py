"""Live pipeline orchestrator — processes TShark events through the Cyber World Model."""

import logging
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from netwatch.live.config import (
    LIVE_FORECAST_HORIZON,
    LIVE_MAX_STATE_HISTORY,
    LIVE_MIN_STATES_FOR_MODEL,
    LIVE_MODEL_REFIT_INTERVAL,
)
from netwatch.live.event_parser import parse_ek_line
from netwatch.live.flow_tracker import FlowTracker
from netwatch.live.live_state import LiveAnalysisState, LiveStatus
from netwatch.live.normalizer import event_to_packet_record
from netwatch.live.window_manager import WindowManager
from netwatch.ingestion.parser import PacketRecord

logger = logging.getLogger(__name__)


class LivePipeline:
    """Processes live TShark events through the full Cyber World Model pipeline."""

    def __init__(self, state: LiveAnalysisState):
        self.state = state
        self.window_mgr = WindowManager(
            window_size=state.window_size,
            step_size=state.step_size,
        )
        self.flow_tracker = FlowTracker()
        self._records_buffer: deque = deque(maxlen=8000)
        self._pipeline = None
        self._world_model_ready = False
        self._window_count = 0
        self._states_since_last_fit = 0

    def process_event(self, event: dict):
        """Process a single TShark event through the pipeline.

        The sensor delivers raw JSON (one object per line, EK control frames
        interleaved). parse_ek_line extracts the flat packet dict; control
        frames and unparseable lines are ignored.
        """
        self.state.events_received += 1
        parsed = parse_ek_line(event)
        if parsed is None:
            return
        pr = event_to_packet_record(parsed)
        if pr is None:
            return
        self.window_mgr.add_event(parsed)
        self.flow_tracker.process_event(parsed)
        self._records_buffer.append(pr)
        self.state.packets += 1
        self.state.bytes_total += pr.bytes_sent

    def check_window(self):
        """Check if a window step has elapsed and process if so."""
        window_events = self.window_mgr.check_step()
        if window_events is None:
            return

        self._window_count += 1
        window_records = self._extract_records(window_events)

        if not window_records:
            self.state.log_event("window", f"Window {self._window_count}: no parseable records")
            return

        self.state.log_event("window", f"Window {self._window_count}: {len(window_records)} records")

        self._update_telemetry()

        try:
            self._build_network_state(window_records)
        except Exception as e:
            logger.warning("Failed to build network state: %s", e)
            self.state.log_event("error", f"NetworkState build failed: {e}")
            return

        if self._world_model_ready:
            try:
                self._run_analysis()
            except Exception as e:
                logger.warning("Analysis failed: %s", e)
                self.state.log_event("error", f"Analysis failed: {e}")

    def force_window(self):
        """Force process any buffered events as a window (for testing / manual trigger)."""
        events = self.window_mgr.get_current_window_events()
        if events:
            window_records = self._extract_records(events)
            if window_records:
                self._window_count += 1
                self._build_network_state(window_records)
                if self._world_model_ready:
                    self._run_analysis()

    def _extract_records(self, events: list) -> List[PacketRecord]:
        records = []
        for ev in events:
            pr = event_to_packet_record(ev)
            if pr:
                records.append(pr)
        return records

    def _update_telemetry(self):
        stats = self.window_mgr.stats
        flow_stats = self.flow_tracker.get_stats()
        self.state.events_received = stats["events_received"]
        self.state.events_processed = stats["events_processed"]
        self.state.events_dropped = stats["events_dropped"]
        self.state.flows = flow_stats["active_flows"]
        self.state.hosts = flow_stats["hosts_seen"]
        ws = self.state.window_size
        if ws > 0:
            self.state.packets_per_second = self.state.packets / max(
                time.time() - (datetime.fromisoformat(
                    self.state.started_at).timestamp() if self.state.started_at else time.time()), 1)
            self.state.bytes_per_second = self.state.bytes_total / max(
                time.time() - (datetime.fromisoformat(
                    self.state.started_at).timestamp() if self.state.started_at else time.time()), 1)

    def _build_network_state(self, records: List[PacketRecord]):
        """Build a NetworkState from a window of records using existing StateBuilder."""
        from netwatch.features.network_state import StateBuilder

        self.state.status = LiveStatus.ANALYZING

        builder = StateBuilder(
            window_seconds=self.state.window_size,
            window_step=self.state.window_size,
            group_by_pair=False,
            enable_advanced_features=True,
        )
        # Create a fresh builder for the window (no persistence needed)
        window_states = builder.build_states(records)
        if not window_states:
            self.state.log_event("warning", "No NetworkState produced from window")
            return

        latest_state = window_states[-1]
        self.state.states_count += 1

        # Maintain pipeline state history
        if self._pipeline is None:
            from netwatch.pipeline import Pipeline
            self._pipeline = Pipeline()

        self._pipeline.states.append(latest_state)
        if len(self._pipeline.states) > LIVE_MAX_STATE_HISTORY:
            self._pipeline.states = self._pipeline.states[-LIVE_MAX_STATE_HISTORY:]

        self._states_since_last_fit += 1
        n_states = len(self._pipeline.states)

        if n_states >= LIVE_MIN_STATES_FOR_MODEL and not self._world_model_ready:
            self._fit_world_model()
        elif self._world_model_ready and self._states_since_last_fit >= LIVE_MODEL_REFIT_INTERVAL:
            self._fit_world_model()

        # Update state payload for dashboard
        self.state.network_state = {
            "features": latest_state.features,
            "timestamp": latest_state.timestamp,
        }
        self.state.log_event("state", f"NetworkState #{self.state.states_count} built")

    def _fit_world_model(self):
        """Fit/re-fit the world model on current state history."""
        try:
            from netwatch.features.sequences import (
                StateNormalizer, build_sequences, assign_labels_and_stages,
            )
            from netwatch.models.trainer import WorldModelTrainer
            from netwatch.config import SEQUENCE_LENGTH, get_feature_columns

            states = self._pipeline.states
            if len(states) < 3:
                return

            # Assign labels via heuristic
            assign_labels_and_stages(states, stage_vocab=None)

            # Fit normalizer
            self._pipeline.normalizer.fit(states)
            self._pipeline.feature_columns = get_feature_columns()
            self._pipeline.n_features = len(self._pipeline.feature_columns)

            seq_len = min(SEQUENCE_LENGTH, max(1, len(states) - 1))
            X, Y = build_sequences(states, self._pipeline.normalizer,
                                   sequence_length=seq_len)
            if X.shape[0] == 0:
                return

            # Train linear world model (fast)
            self._pipeline.trainer = WorldModelTrainer(
                model_type="linear",
                n_features=self._pipeline.n_features,
            )
            self._pipeline.trainer.fit(X, Y, val_fraction=0.15, batch_size=32, epochs=1)

            # Setup attack forecaster
            from netwatch.forecasting.attack_forecaster import AttackForecaster
            from netwatch.forecasting.stage_predictor import StagePredictor
            self._pipeline.stage_predictor = StagePredictor()
            self._pipeline.attack_forecaster = AttackForecaster(
                self._pipeline.trainer.model,
                self._pipeline.normalizer,
                self._pipeline.stage_predictor,
                feature_columns=self._pipeline.feature_columns,
            )
            # Fit risk head if we have at least 2 label classes
            from netwatch.features.sequences import build_seq_labels
            labels = build_seq_labels(states, sequence_length=seq_len)
            if len(np.unique(labels)) >= 2:
                self._pipeline.attack_forecaster.fit_risk_head(states)

            # Setup explainers
            from netwatch.explainability.shap_explainer import ShapExplainer
            from netwatch.explainability.temporal_explainer import TemporalExplainer
            self._pipeline.explainer = ShapExplainer(
                risk_model=(self._pipeline.attack_forecaster.risk_model
                            if self._pipeline.attack_forecaster._risk_trained
                            else None),
                feature_columns=self._pipeline.feature_columns,
                normalizer=self._pipeline.normalizer,
            )
            self._pipeline.temporal_explainer = TemporalExplainer(
                shap_explainer=self._pipeline.explainer,
                feature_columns=self._pipeline.feature_columns,
            )

            self._world_model_ready = True
            self.state.world_model_status = "ready"
            self._states_since_last_fit = 0
            self.state.log_event("model", f"World model fitted on {len(states)} states (seq_len={seq_len})")

        except Exception as e:
            logger.warning("World model fit failed: %s", e)
            self.state.log_event("error", f"World model fit failed: {e}")
            self._world_model_ready = False

    def _run_analysis(self):
        """Run forecast, risk, stage, graph, MITRE, explainability, counterfactual."""
        pipe = self._pipeline
        states = pipe.states
        if not states or not pipe.attack_forecaster:
            return

        seq_len = min(10, max(1, len(states) - 1))
        history = states[-seq_len:]

        # Forecast
        try:
            forecast_result = pipe.attack_forecaster.forecast(history, k=self.state.forecast_horizon)
        except Exception as e:
            logger.warning("Forecast failed: %s", e)
            self.state.log_event("error", f"Forecast failed: {e}")
            return

        self.state.forecast = forecast_result
        current = forecast_result.get("current", {})
        future = forecast_result.get("future", [])

        # Risk
        self.state.risk = {
            "current_risk": current.get("risk", 0),
            "future_max_risk": max([current.get("risk", 0)] + [s.get("risk", 0) for s in future]),
            "risk_trend": self._compute_risk_trend(future),
            "confidence": current.get("confidence", 0),
            "forecast_horizon": self.state.forecast_horizon,
        }

        # Stage
        self.state.stage = {
            "predicted_stage": current.get("stage", "Unknown"),
            "stage_probability": current.get("stage_probability", 0),
            "future_stages": [s.get("stage", "Unknown") for s in future],
        }

        # Graph
        try:
            from netwatch.graph.predictive_attack_graph import build_predictive_graph
            self.state.graph = build_predictive_graph(forecast_result)
        except Exception as e:
            logger.warning("Graph build failed: %s", e)

        # MITRE
        try:
            from netwatch.mitre.attack_mapper import AttackMapper
            mapper = AttackMapper()
            stages = [current.get("stage")] + [s.get("stage") for s in future]
            self.state.mitre = mapper.map_trajectory(stages)
        except Exception as e:
            logger.warning("MITRE mapping failed: %s", e)

        # Explainability
        try:
            if pipe.explainer:
                self.state.explainability = pipe.explainer.explain(
                    current.get("state_vec", []),
                    current.get("features", {}),
                )
        except Exception as e:
            logger.warning("Explainability failed: %s", e)

        # Counterfactual
        try:
            from netwatch.counterfactual.simulator import CounterfactualEngine
            from netwatch.config import DEFAULT_ACTIONS
            engine = CounterfactualEngine(
                pipe.trainer.model, pipe.attack_forecaster,
                pipe.normalizer, feature_columns=pipe.feature_columns,
            )
            sim = engine.simulate(history, actions=DEFAULT_ACTIONS, k=self.state.forecast_horizon)
            rec = engine.recommend(sim)
            self.state.counterfactual = {**sim, "recommendation": rec}
        except Exception as e:
            logger.warning("Counterfactual failed: %s", e)

        # Ensemble
        try:
            from netwatch.forecasting.ensemble_scorer import EnsembleScorer
            scorer = EnsembleScorer(pipeline=pipe)
            recent_records = list(self._records_buffer)[-2000:]
            self.state.ensemble = scorer.evaluate_traffic(
                records=recent_records, states=states[-20:], k_steps=self.state.forecast_horizon,
            )
        except Exception as e:
            logger.warning("Ensemble scoring failed: %s", e)

        # Assemble doc
        self._assemble_doc()
        self.state.log_event("analysis", f"Analysis complete: risk={self.state.risk.get('current_risk', 0):.3f}")

    def _compute_risk_trend(self, future: list) -> str:
        if not future:
            return "stable"
        current_risk = self.state.risk.get("current_risk", 0) if self.state.risk else 0
        final_risk = future[-1].get("risk", 0)
        if final_risk > current_risk + 0.05:
            return "escalating"
        if final_risk < current_risk - 0.05:
            return "mitigating"
        return "stable"

    def _assemble_doc(self):
        """Assemble the canonical analysis document from cached results."""
        self.state._doc = self.state.to_analysis_dict()

    @property
    def doc(self) -> Optional[dict]:
        return self.state._doc or self.state.to_analysis_dict()

    def reset(self):
        self.window_mgr.reset()
        self.flow_tracker.reset()
        self._records_buffer.clear()
        self._pipeline = None
        self._world_model_ready = False
        self._window_count = 0
        self._states_since_last_fit = 0
        self.state.world_model_status = "not_ready"
