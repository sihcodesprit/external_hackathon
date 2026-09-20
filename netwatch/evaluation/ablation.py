"""
Ablation Study Framework.

Systematically evaluates the contribution of each feature group and model component
by training/evaluating with different feature subsets.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from netwatch.config import REPORTS_DIR, ensure_dirs, get_feature_registry
from netwatch.evaluation.metrics import evaluate_state_predictions
from netwatch.features.sequences import (
    StateNormalizer,
    build_seq_labels,
    build_sequences,
    temporal_split,
)
from netwatch.forecasting.attack_forecaster import AttackForecaster
from netwatch.forecasting.stage_predictor import StagePredictor
from netwatch.models.trainer import WorldModelTrainer
from netwatch.pipeline import Pipeline

logger = logging.getLogger(__name__)


@dataclass
class AblationResult:
    """Results from a single ablation experiment."""
    experiment_name: str
    feature_groups: List[str]
    n_features: int
    training_time: float
    continuous_metrics: Dict[str, float]
    classification_metrics: Dict[str, float]
    forecast_metrics: Optional[Dict] = None
    counterfactual_metrics: Optional[Dict] = None
    notes: str = ""


@dataclass
class AblationConfig:
    """Configuration for an ablation study."""
    name: str
    description: str
    feature_sets: List[List[str]]  # List of feature group combinations to test
    baseline_model: str = "lstm"
    epochs: int = 30
    sequence_length: int = 10
    forecast_horizon: int = 5
    n_traces: int = 4
    duration_minutes: float = 120.0


# Predefined ablation configurations from config.yaml
DEFAULT_ABLATION_FEATURE_SETS = [
    ["traffic"],
    ["traffic", "packet"],
    ["traffic", "packet", "entropy"],
    ["traffic", "packet", "entropy", "temporal"],
    ["traffic", "packet", "entropy", "temporal", "graph"],
    ["traffic", "packet", "entropy", "temporal", "graph",
     "tcp_handshake", "markov", "trajectory", "baseline_deviation"],
]


DEFAULT_ABLATION_TYPES = [
    "feature_ablation",
    "graph_ablation",
    "entropy_ablation",
    "temporal_ablation",
    "model_vs_baselines",
]


class AblationStudy:
    """Runs ablation studies on the World Model."""

    def __init__(self, config: Optional[AblationConfig] = None):
        self.config = config or AblationConfig(
            name="default_ablation",
            description="Default feature ablation study",
            feature_sets=DEFAULT_ABLATION_FEATURE_SETS,
        )
        self.results: List[AblationResult] = []
        self.pipeline = Pipeline()

    def run_feature_ablation(self, states: List) -> List[AblationResult]:
        """Run feature ablation: progressively add feature groups."""
        results = []

        for i, feature_groups in enumerate(self.config.feature_sets):
            exp_name = f"{self.config.name}_feature_set_{i+1}"
            logger.info(f"Running ablation: {exp_name} with groups: {feature_groups}")

            # Build registry with only these feature groups
            registry = get_feature_registry()
            # Disable all groups first
            for group_name in registry.groups:
                if not registry.groups[group_name].required:
                    registry.enable_group(group_name, False)
            # Enable selected groups
            for group_name in feature_groups:
                registry.enable_group(group_name, True)

            # Get enabled feature columns
            feature_cols = registry.get_enabled_features()
            n_features = len(feature_cols)

            # Build normalizer with these features
            normalizer = StateNormalizer()
            normalizer.fit(states)

            # Build sequences
            X, Y = build_sequences(states, normalizer,
                                   sequence_length=self.config.sequence_length,
                                   horizon=1)

            if X.shape[0] == 0:
                logger.warning(f"Not enough sequences for {exp_name}")
                continue

            # Split
            train_states, val_states = temporal_split(states, val_fraction=0.2)
            X_train, Y_train = build_sequences(train_states, normalizer,
                                                sequence_length=self.config.sequence_length)
            X_val, Y_val = build_sequences(val_states, normalizer,
                                            sequence_length=self.config.sequence_length)


            bin_val = build_seq_labels(val_states,
                                       sequence_length=self.config.sequence_length)

            # Train model
            start_time = time.time()
            trainer = WorldModelTrainer(
                model_type=self.config.baseline_model,
                n_features=n_features,
                hidden_size=64,
                num_layers=2,
                dropout=0.2,
                learning_rate=1e-3,
            )
            trainer.fit(X_train, Y_train,
                                         batch_size=32, epochs=self.config.epochs,
                                         val_fraction=0.15)
            training_time = time.time() - start_time

            # Evaluate
            pred_states = [trainer.model.predict_next_state(x) for x in X_val]
            true_states = Y_val
            true_labels = bin_val

            # Get risk head
            forecaster = AttackForecaster(trainer.model, normalizer, StagePredictor())
            forecaster.fit_risk_head(states)

            eval_results = evaluate_state_predictions(
                pred_states, true_states, true_labels,
                risk_head=lambda s: forecaster._attack_prob(s)
            )

            result = AblationResult(
                experiment_name=exp_name,
                feature_groups=feature_groups,
                n_features=n_features,
                training_time=training_time,
                continuous_metrics=eval_results["continuous"],
                classification_metrics=eval_results["classification"],
            )
            results.append(result)
            logger.info(f"  MSE: {eval_results['continuous']['mse']:.4f}, "
                        f"Acc: {eval_results['classification']['accuracy']:.4f}")

        # Restore all features
        registry = get_feature_registry()
        for group_name in registry.groups:
            registry.enable_group(group_name, True)

        return results

    def run_graph_ablation(self, states: List) -> List[AblationResult]:
        """Run graph feature ablation: with/without graph features."""
        results = []

        for use_graph in [False, True]:
            exp_name = f"{self.config.name}_graph_{'with' if use_graph else 'without'}"
            feature_groups = ["traffic", "packet", "entropy", "temporal"]
            if use_graph:
                feature_groups.append("graph")

            logger.info(f"Running graph ablation: {exp_name}")

            registry = get_feature_registry()
            for group_name in registry.groups:
                if not registry.groups[group_name].required:
                    registry.enable_group(group_name, False)
            for group_name in feature_groups:
                registry.enable_group(group_name, True)

            feature_cols = registry.get_enabled_features()
            n_features = len(feature_cols)

            normalizer = StateNormalizer()
            normalizer.fit(states)

            X, Y = build_sequences(states, normalizer,
                                   sequence_length=self.config.sequence_length,
                                   horizon=1)
            train_states, val_states = temporal_split(states, val_fraction=0.2)
            X_train, Y_train = build_sequences(train_states, normalizer,
                                                sequence_length=self.config.sequence_length)
            X_val, Y_val = build_sequences(val_states, normalizer,
                                            sequence_length=self.config.sequence_length)

            bin_val = build_seq_labels(val_states,
                                       sequence_length=self.config.sequence_length)

            start_time = time.time()
            trainer = WorldModelTrainer(
                model_type=self.config.baseline_model,
                n_features=n_features,
            )
            trainer.fit(X_train, Y_train, batch_size=32, epochs=self.config.epochs,
                         val_fraction=0.15)
            training_time = time.time() - start_time

            pred_states = [trainer.model.predict_next_state(x) for x in X_val]
            forecaster = AttackForecaster(trainer.model, normalizer, StagePredictor())
            forecaster.fit_risk_head(states)

            eval_results = evaluate_state_predictions(
                pred_states, Y_val, bin_val,
                risk_head=lambda s: forecaster._attack_prob(s)
            )

            result = AblationResult(
                experiment_name=exp_name,
                feature_groups=feature_groups,
                n_features=n_features,
                training_time=training_time,
                continuous_metrics=eval_results["continuous"],
                classification_metrics=eval_results["classification"],
                notes=f"Graph features: {'enabled' if use_graph else 'disabled'}",
            )
            results.append(result)

        # Restore
        registry = get_feature_registry()
        for group_name in registry.groups:
            registry.enable_group(group_name, True)

        return results

    def run_entropy_ablation(self, states: List) -> List[AblationResult]:
        """Run entropy feature ablation: without / with / with temporal entropy."""
        results = []

        configs = [
            ("without_entropy", ["traffic", "packet", "temporal", "graph"]),
            ("with_entropy", ["traffic", "packet", "entropy", "temporal", "graph"]),
            # "with_temporal_entropy" would need trajectory features
        ]

        for exp_suffix, feature_groups in configs:
            exp_name = f"{self.config.name}_entropy_{exp_suffix}"
            logger.info(f"Running entropy ablation: {exp_name}")

            registry = get_feature_registry()
            for group_name in registry.groups:
                if not registry.groups[group_name].required:
                    registry.enable_group(group_name, False)
            for group_name in feature_groups:
                registry.enable_group(group_name, True)

            feature_cols = registry.get_enabled_features()
            n_features = len(feature_cols)

            normalizer = StateNormalizer()
            normalizer.fit(states)

            X, Y = build_sequences(states, normalizer,
                                   sequence_length=self.config.sequence_length,
                                   horizon=1)
            train_states, val_states = temporal_split(states, val_fraction=0.2)
            X_train, Y_train = build_sequences(train_states, normalizer,
                                                sequence_length=self.config.sequence_length)
            X_val, Y_val = build_sequences(val_states, normalizer,
                                            sequence_length=self.config.sequence_length)

            bin_val = build_seq_labels(val_states,
                                       sequence_length=self.config.sequence_length)

            start_time = time.time()
            trainer = WorldModelTrainer(
                model_type=self.config.baseline_model,
                n_features=n_features,
            )
            trainer.fit(X_train, Y_train, batch_size=32, epochs=self.config.epochs,
                         val_fraction=0.15)
            training_time = time.time() - start_time

            pred_states = [trainer.model.predict_next_state(x) for x in X_val]
            forecaster = AttackForecaster(trainer.model, normalizer, StagePredictor())
            forecaster.fit_risk_head(states)

            eval_results = evaluate_state_predictions(
                pred_states, Y_val, bin_val,
                risk_head=lambda s: forecaster._attack_prob(s)
            )

            result = AblationResult(
                experiment_name=exp_name,
                feature_groups=feature_groups,
                n_features=n_features,
                training_time=training_time,
                continuous_metrics=eval_results["continuous"],
                classification_metrics=eval_results["classification"],
                notes=f"Entropy config: {exp_suffix}",
            )
            results.append(result)

        # Restore
        registry = get_feature_registry()
        for group_name in registry.groups:
            registry.enable_group(group_name, True)

        return results

    def run_temporal_ablation(self, states: List) -> List[AblationResult]:
        """Run temporal feature ablation."""
        results = []

        configs = [
            ("raw_only", ["traffic", "packet", "entropy", "graph"]),
            ("with_iat", ["traffic", "packet", "entropy", "temporal", "graph"]),
            # Could add more: with_autocorr, with_periodicity, etc.
        ]

        for exp_suffix, feature_groups in configs:
            exp_name = f"{self.config.name}_temporal_{exp_suffix}"
            logger.info(f"Running temporal ablation: {exp_name}")

            registry = get_feature_registry()
            for group_name in registry.groups:
                if not registry.groups[group_name].required:
                    registry.enable_group(group_name, False)
            for group_name in feature_groups:
                registry.enable_group(group_name, True)

            feature_cols = registry.get_enabled_features()
            n_features = len(feature_cols)

            normalizer = StateNormalizer()
            normalizer.fit(states)

            X, Y = build_sequences(states, normalizer,
                                   sequence_length=self.config.sequence_length,
                                   horizon=1)
            train_states, val_states = temporal_split(states, val_fraction=0.2)
            X_train, Y_train = build_sequences(train_states, normalizer,
                                                sequence_length=self.config.sequence_length)
            X_val, Y_val = build_sequences(val_states, normalizer,
                                            sequence_length=self.config.sequence_length)

            bin_val = build_seq_labels(val_states,
                                       sequence_length=self.config.sequence_length)

            start_time = time.time()
            trainer = WorldModelTrainer(
                model_type=self.config.baseline_model,
                n_features=n_features,
            )
            trainer.fit(X_train, Y_train, batch_size=32, epochs=self.config.epochs,
                         val_fraction=0.15)
            training_time = time.time() - start_time

            pred_states = [trainer.model.predict_next_state(x) for x in X_val]
            forecaster = AttackForecaster(trainer.model, normalizer, StagePredictor())
            forecaster.fit_risk_head(states)

            eval_results = evaluate_state_predictions(
                pred_states, Y_val, bin_val,
                risk_head=lambda s: forecaster._attack_prob(s)
            )

            result = AblationResult(
                experiment_name=exp_name,
                feature_groups=feature_groups,
                n_features=n_features,
                training_time=training_time,
                continuous_metrics=eval_results["continuous"],
                classification_metrics=eval_results["classification"],
                notes=f"Temporal config: {exp_suffix}",
            )
            results.append(result)

        # Restore
        registry = get_feature_registry()
        for group_name in registry.groups:
            registry.enable_group(group_name, True)

        return results

    def run_model_vs_baselines(self, states: List) -> List[AblationResult]:
        """Compare World Model against baseline classifiers."""
        from netwatch.evaluation.baselines import train_and_evaluate_baseline

        results = []

        # Use full feature set
        registry = get_feature_registry()
        feature_cols = registry.get_enabled_features()
        n_features = len(feature_cols)

        normalizer = StateNormalizer()
        normalizer.fit(states)

        X, Y = build_sequences(states, normalizer,
                               sequence_length=self.config.sequence_length,
                               horizon=1)
        train_states, val_states = temporal_split(states, val_fraction=0.2)
        X_train, Y_train = build_sequences(train_states, normalizer,
                                            sequence_length=self.config.sequence_length)
        X_val, Y_val = build_sequences(val_states, normalizer,
                                        sequence_length=self.config.sequence_length)
        bin_train = build_seq_labels(train_states,
                                     sequence_length=self.config.sequence_length)
        bin_val = build_seq_labels(val_states,
                                   sequence_length=self.config.sequence_length)

        # World Model
        trainer = WorldModelTrainer(
            model_type=self.config.baseline_model,
            n_features=n_features,
        )
        trainer.fit(X_train, Y_train, batch_size=32, epochs=self.config.epochs,
                     val_fraction=0.15)

        pred_states = [trainer.model.predict_next_state(x) for x in X_val]
        forecaster = AttackForecaster(trainer.model, normalizer, StagePredictor())
        forecaster.fit_risk_head(states)

        eval_results = evaluate_state_predictions(
            pred_states, Y_val, bin_val,
            risk_head=lambda s: forecaster._attack_prob(s)
        )

        wm_result = AblationResult(
            experiment_name=f"{self.config.name}_world_model",
            feature_groups=registry.get_canonical_group_order(),
            n_features=n_features,
            training_time=0.0,  # Not measured here
            continuous_metrics=eval_results["continuous"],
            classification_metrics=eval_results["classification"],
            notes="LSTM World Model with full features",
        )
        results.append(wm_result)

        # Baseline classifiers on flattened features
        flat_train_X = X_train.reshape(X_train.shape[0], -1)
        flat_val_X = X_val.reshape(X_val.shape[0], -1)

        for baseline_name in ["logistic_regression", "random_forest", "gradient_boosting"]:
            try:
                baseline_result = train_and_evaluate_baseline(
                    baseline_name, flat_train_X, bin_train,
                    flat_val_X, bin_val
                )
                result = AblationResult(
                    experiment_name=f"{self.config.name}_baseline_{baseline_name}",
                    feature_groups=registry.get_canonical_group_order(),
                    n_features=flat_train_X.shape[1],
                    training_time=0.0,
                    continuous_metrics={},  # Not applicable
                    classification_metrics={
                        "accuracy": baseline_result["accuracy"],
                        "precision": baseline_result["precision"],
                        "recall": baseline_result["recall"],
                        "f1": baseline_result["f1"],
                        "roc_auc": baseline_result.get("roc_auc", float("nan")),
                    },
                    notes=f"Baseline: {baseline_name} on flattened windows",
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"Baseline {baseline_name} failed: {e}")

        return results

    def run_all_ablations(self, states: List) -> Dict[str, List[AblationResult]]:
        """Run all configured ablation studies."""
        all_results = {}

        if "feature_ablation" in DEFAULT_ABLATION_TYPES:
            all_results["feature_ablation"] = self.run_feature_ablation(states)

        if "graph_ablation" in DEFAULT_ABLATION_TYPES:
            all_results["graph_ablation"] = self.run_graph_ablation(states)

        if "entropy_ablation" in DEFAULT_ABLATION_TYPES:
            all_results["entropy_ablation"] = self.run_entropy_ablation(states)

        if "temporal_ablation" in DEFAULT_ABLATION_TYPES:
            all_results["temporal_ablation"] = self.run_temporal_ablation(states)

        if "model_vs_baselines" in DEFAULT_ABLATION_TYPES:
            all_results["model_vs_baselines"] = self.run_model_vs_baselines(states)

        self.results = []
        for study_results in all_results.values():
            self.results.extend(study_results)

        return all_results

    def save_results(self, path: Optional[Path] = None) -> Path:
        """Save ablation results to JSON."""
        if path is None:
            ensure_dirs()
            path = REPORTS_DIR / f"ablation_results_{int(time.time())}.json"

        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "config": {
                "name": self.config.name,
                "description": self.config.description,
                "feature_sets": self.config.feature_sets,
                "baseline_model": self.config.baseline_model,
                "epochs": self.config.epochs,
            },
            "results": [
                {
                    "experiment_name": r.experiment_name,
                    "feature_groups": r.feature_groups,
                    "n_features": r.n_features,
                    "training_time": r.training_time,
                    "continuous_metrics": r.continuous_metrics,
                    "classification_metrics": r.classification_metrics,
                    "forecast_metrics": r.forecast_metrics,
                    "counterfactual_metrics": r.counterfactual_metrics,
                    "notes": r.notes,
                }
                for r in self.results
            ],
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Ablation results saved to {path}")
        return path

    def print_summary(self):
        """Print a summary table of ablation results."""
        print("\n" + "=" * 100)
        print("ABLATION STUDY SUMMARY")
        print("=" * 100)
        print(f"{'Experiment':<40} {'Features':>8} {'MSE':>10} {'RMSE':>10} {'Acc':>8} {'F1':>8} {'Time(s)':>8}")
        print("-" * 100)

        for r in self.results:
            mse = r.continuous_metrics.get("mse", float("nan"))
            rmse = r.continuous_metrics.get("rmse", float("nan"))
            acc = r.classification_metrics.get("accuracy", float("nan"))
            f1 = r.classification_metrics.get("f1", float("nan"))
            print(f"{r.experiment_name:<40} {r.n_features:>8} {mse:>10.4f} {rmse:>10.4f} "
                  f"{acc:>8.4f} {f1:>8.4f} {r.training_time:>8.1f}")

        print("=" * 100)


def run_ablation_study_from_pipeline(pipeline: Pipeline,
                                      config: Optional[AblationConfig] = None) -> AblationStudy:
    """Convenience function to run ablation study using a prepared pipeline."""
    study = AblationStudy(config)
    study.run_all_ablations(pipeline.states)
    study.save_results()
    study.print_summary()
    return study
