"""
Top-level pipeline orchestrator.

Ties the whole system together end-to-end:

    synthetic ingestion
        -> build NetworkStates
        -> normalize + build sequences
        -> train World Model (LSTM)
        -> fit risk head + stage predictor
        -> evaluate (continuous + classification) + baselines + unseen attack
        -> optional K-step forecast + counterfactual defensive simulation
        -> save artifacts

No data is fabricated. Every number in the returned report is computed from
actual model outputs.
"""

import datetime as _dt
import json
import logging
from dataclasses import asdict
from typing import Dict, Optional

import numpy as np

from netwatch.config import (
    DEFAULT_ACTIONS,
    FEATURE_COLUMNS,
    K_STEP_HORIZON,
    MODEL_DIR,
    N_FEATURES,
    REPORTS_DIR,
    SCALER_PATH,
    WORLD_MODEL_PATH,
    WORLD_MODEL_TYPE,
    ensure_dirs,
)
from netwatch.counterfactual.simulator import CounterfactualEngine
from netwatch.explainability.shap_explainer import ShapExplainer
from netwatch.features.network_state import StateBuilder
from netwatch.features.sequences import (
    StateNormalizer,
    assign_labels_and_stages,
    build_sequences,
    build_seq_labels,
    split_by_group,
    temporal_split,
)
from netwatch.forecasting.attack_forecaster import AttackForecaster
from netwatch.forecasting.stage_predictor import StagePredictor
from netwatch.ingestion.synthetic import generate_trace
from netwatch.models.trainer import WorldModelTrainer
from netwatch.mitre.attack_mapper import AttackMapper

logger = logging.getLogger(__name__)


def _safe_bin(labels):
    """Reshape labels to 1D int array for classification metrics."""
    arr = np.asarray(labels).ravel()
    return arr.astype(int)


class Pipeline:
    """End-to-end orchestrator."""

    def __init__(self, dataset: str = "synthetic", **kwargs):
        ensure_dirs()
        self.dataset = dataset
        self.normalizer = StateNormalizer()
        self.stage_predictor = StagePredictor()
        self.attack_mapper = AttackMapper()
        self.trainer = None
        self.attack_forecaster = None
        self.counterfactual = None
        self.explainer = None
        self.results: Dict = {}

    # ── I. data ────────────────────────────────────────────
    def load_data(self, n_traces: int = 20, seed: int = 42,
                  duration_minutes: float = 120.0, **gen_kwargs) -> dict:
        """Generate (or, in future, ingest) event data and build states.

        Traces are staggered in time so they concatenate into a long, diverse
        timeline rather than overlapping onto the same clock.
        """
        records = []
        for i in range(n_traces):
            records.extend(generate_trace(
                random_seed=seed + i,
                duration_minutes=duration_minutes,
                time_offset_minutes=i * duration_minutes,
                **gen_kwargs))
        builder = StateBuilder(group_by_pair=False)
        states = builder.build_states(records)
        states = assign_labels_and_stages(states, stage_vocab=None)
        self.states = states
        return {
            "n_packets": len(records),
            "n_states": len(states),
            "n_attack_states": sum(1 for s in states if s.label == 1),
            "n_benign_states": sum(1 for s in states if s.label == 0),
        }

    # ── II. train ──────────────────────────────────────────
    def train(self) -> Dict:
        if not hasattr(self, "states") or not self.states:
            raise RuntimeError("load_data() must be called before train()")

        # temporal (session-aware) split for validation
        train_states, val_states = temporal_split(self.states,
                                                  val_fraction=0.2)
        self.normalizer.fit(self.states)

        # sequences for World Model (continuous next-state regression)
        X_train, Y_train = build_sequences(train_states, self.normalizer)
        X_val, Y_val = build_sequences(val_states, self.normalizer)
        if X_train.shape[0] == 0:
            raise RuntimeError("Not enough states to build training sequences")

        # Binary labels aligned with the sequence rows
        from netwatch.features.sequences import build_seq_labels
        bin_train = build_seq_labels(train_states)
        bin_val = build_seq_labels(val_states)

        self.trainer = WorldModelTrainer(
            model_type=WORLD_MODEL_TYPE, n_features=N_FEATURES)

        # Train world model on continuous next-state target
        metrics = self.trainer.fit(X_train, Y_train, val_fraction=0.15,
                                   batch_size=32, epochs=30)

        # Risk head: train logistic regression on normalized states -> label
        self.attack_forecaster = AttackForecaster(
            self.trainer.model, self.normalizer, self.stage_predictor,
            feature_columns=FEATURE_COLUMNS)
        self.attack_forecaster.fit_risk_head(self.states)

        # Stage predictor (heuristic fallback used; no real labelled data yet)
        self.explainer = ShapExplainer(
            risk_model=self.attack_forecaster.risk_model
            if self.attack_forecaster._risk_trained else None,
            feature_columns=FEATURE_COLUMNS, normalizer=self.normalizer)

        self._X_train, self._Y_train = X_train, Y_train
        self._X_val, self._Y_val = X_val, Y_val
        self._bin_train, self._bin_val = bin_train, bin_val

        # persist artifacts
        self.normalizer.save(SCALER_PATH)
        self.trainer.save(str(WORLD_MODEL_PATH))

        return {
            "training": metrics,
            "risk_head_trained": self.attack_forecaster._risk_trained,
            "n_train_sequences": int(X_train.shape[0]),
            "n_val_sequences": int(X_val.shape[0]),
        }

    # ── III. evaluate ──────────────────────────────────────
    def evaluate(self, include_baselines: bool = True,
                 include_unseen: bool = True) -> Dict:
        from netwatch.evaluation.baselines import ModelEvaluator
        from netwatch.evaluation.unseen_attack import UnseenAttackTest

        evaluator = ModelEvaluator(self.trainer, self.normalizer)
        # build a validation/test evaluation using the preserved splits
        eval_result = evaluator.evaluate(
            self._X_train, self._Y_train, self._X_val, self._Y_val,
            bin_train=_safe_bin(self._bin_train),
            bin_test=_safe_bin(self._bin_val))

        result = {"model_evaluation": eval_result}

        if include_unseen:
            unseen = UnseenAttackTest(self.trainer, self.normalizer)
            # hold out one attack stage entirely from training states
            train_states = [s for s in self.states
                            if s.stage not in ("Exfiltration", "Impact")]
            unseen_states = [s for s in self.states
                             if s.stage in ("Exfiltration", "Impact")]

            X_tr, Y_tr = build_sequences(train_states, self.normalizer)
            X_un, Y_un = build_sequences(unseen_states, self.normalizer)
            bin_tr = _safe_bin(build_seq_labels(train_states))
            bin_un = _safe_bin(build_seq_labels(unseen_states))
            if X_tr.shape[0] and X_un.shape[0]:
                result["unseen_attack"] = unseen.run(
                    X_tr, Y_tr, X_un, Y_un, bin_unseen=bin_un)

        self.results["evaluation"] = result
        return result

    # ── IV. forecast + counterfactual ──────────────────────
    def forecast_and_simulate(self, k: int = K_STEP_HORIZON) -> Dict:
        """Run a K-step forecast on the most recent window and counterfactual
        defensive simulation."""
        if not self.states:
            raise RuntimeError("No data loaded")

        # pick a recent window where the attack is ONGOING (the next state is
        # also an attack), so the counterfactual meaningfully contrasts
        # continued risk vs containment. Fall back to the last attack window,
        # then the timeline tail.
        seq_len = self._X_train.shape[1] if hasattr(self, "_X_train") else 10
        attack_idx = None
        for i in range(len(self.states) - 2, -1, -1):
            if int(self.states[i].label or 0) == 1 and \
               int(self.states[i + 1].label or 0) == 1 and i >= seq_len - 1:
                attack_idx = i
                break
        if attack_idx is None:
            for i in range(len(self.states) - 1, -1, -1):
                if int(self.states[i].label or 0) == 1 and i >= seq_len - 1:
                    attack_idx = i
                    break
        end = attack_idx + 1 if attack_idx is not None else len(self.states)
        history = self.states[end - seq_len:end]

        forecast = self.attack_forecaster.forecast(history, k=k)

        # predictive attack graph
        from netwatch.graph.predictive_attack_graph import build_predictive_graph
        graph = build_predictive_graph(forecast)

        # attach SHAP explanations to each forecast step
        for step in forecast["future"]:
            step["explanation"] = self.explainer.explain(
                step["state_vec"], step["features"])
        forecast["current"]["explanation"] = self.explainer.explain(
            forecast["current"]["state_vec"],
            forecast["current"]["features"])

        # counterfactual defensive simulation
        self.counterfactual = CounterfactualEngine(
            self.trainer.model, self.attack_forecaster, self.normalizer)
        sim = self.counterfactual.simulate(history, actions=DEFAULT_ACTIONS, k=k)
        rec = self.counterfactual.recommend(sim)

        # map current + future stages to MITRE
        stages = [forecast["current"]["stage"]] + \
                 [st["stage"] for st in forecast["future"]]
        mitre = self.attack_mapper.map_trajectory(stages)

        out = {
            "forecast": forecast,
            "graph": graph,
            "counterfactual": {**sim, "recommendation": rec},
            "mitre_trajectory": mitre,
        }
        self.results["forecast"] = out
        return out

    # ── persistence ────────────────────────────────────────
    def save_report(self) -> str:
        from netwatch.config import REPORTS_DIR
        path = REPORTS_DIR / f"pipeline_report_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(self.results, default=str, indent=2))
        return str(path)
