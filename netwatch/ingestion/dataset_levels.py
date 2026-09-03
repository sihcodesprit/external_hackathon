"""
Dataset Level Support — Different tiers of dataset complexity for training and evaluation.

Provides dataset configurations for different complexity levels:
- Level 1: Basic traffic features only (sanity check)
- Level 2: + Packet-level features
- Level 3: + Entropy features  
- Level 4: + Temporal/jitter features
- Level 5: + Graph features
- Level 6: + All advanced features (TCP handshake, Markov, trajectory, baseline)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from netwatch.features.feature_registry import FeatureRegistry, FeatureGroup, REGISTRY


@dataclass
class DatasetLevel:
    """Defines a dataset complexity level with enabled feature groups."""
    name: str
    description: str
    enabled_groups: List[str]
    sequence_length: int = 10
    forecast_horizon: int = 5
    window_seconds: int = 30
    window_step_seconds: int = 10
    epochs: int = 30
    batch_size: int = 64
    hidden_size: int = 128
    num_layers: int = 2
    dropout: float = 0.2
    learning_rate: float = 1e-3
    # Which datasets to use at this level
    datasets: List[str] = field(default_factory=lambda: ["synthetic"])
    # Expected performance targets (for validation)
    target_metrics: Dict[str, float] = field(default_factory=dict)
    
    def create_registry(self) -> FeatureRegistry:
        """Create a feature registry with only the enabled groups."""
        registry = FeatureRegistry()
        for group_name in self.enabled_groups:
            base_group = REGISTRY.groups.get(group_name)
            if base_group:
                registry.register_group(FeatureGroup(
                    name=base_group.name,
                    description=base_group.description,
                    features=base_group.features.copy(),
                    enabled=True,
                    required=base_group.required,
                ))
            else:
                # Required groups not in base registry (e.g., "traffic")
                pass
        # Also include required groups
        for group_name, base_group in REGISTRY.groups.items():
            if base_group.required and group_name not in self.enabled_groups:
                registry.register_group(FeatureGroup(
                    name=base_group.name,
                    description=base_group.description,
                    features=base_group.features.copy(),
                    enabled=True,
                    required=True,
                ))
        return registry


# Predefined dataset levels
DATASET_LEVELS = {
    "level_1_basic": DatasetLevel(
        name="level_1_basic",
        description="Basic traffic volume features only - for quick sanity checks",
        enabled_groups=["traffic"],
        sequence_length=5,
        forecast_horizon=3,
        epochs=10,
        target_metrics={"mse": 0.5, "accuracy": 0.85},
    ),
    "level_2_packet": DatasetLevel(
        name="level_2_packet",
        description="Traffic + packet-level header features",
        enabled_groups=["traffic", "packet"],
        sequence_length=8,
        forecast_horizon=4,
        epochs=20,
        target_metrics={"mse": 0.3, "accuracy": 0.90},
    ),
    "level_3_entropy": DatasetLevel(
        name="level_3_entropy",
        description="Traffic + packet + entropy features for randomness detection",
        enabled_groups=["traffic", "packet", "entropy"],
        sequence_length=10,
        forecast_horizon=5,
        epochs=30,
        target_metrics={"mse": 0.2, "accuracy": 0.92},
    ),
    "level_4_temporal": DatasetLevel(
        name="level_4_temporal",
        description="Traffic + packet + entropy + temporal/jitter features",
        enabled_groups=["traffic", "packet", "entropy", "temporal"],
        sequence_length=10,
        forecast_horizon=5,
        epochs=40,
        target_metrics={"mse": 0.15, "accuracy": 0.94},
    ),
    "level_5_graph": DatasetLevel(
        name="level_5_graph",
        description="Traffic + packet + entropy + temporal + dynamic graph topology",
        enabled_groups=["traffic", "packet", "entropy", "temporal", "graph"],
        sequence_length=12,
        forecast_horizon=5,
        epochs=50,
        target_metrics={"mse": 0.12, "accuracy": 0.95},
    ),
    "level_6_full": DatasetLevel(
        name="level_6_full",
        description="All features - full Counterfactual Cyber World Model",
        enabled_groups=[
            "traffic", "packet", "flow", "tcp_handshake", "entropy",
            "temporal", "graph", "markov", "trajectory", "baseline_deviation"
        ],
        sequence_length=10,
        forecast_horizon=5,
        epochs=50,
        target_metrics={"mse": 0.1, "accuracy": 0.96},
    ),
}


def get_level(level_name: str) -> Optional[DatasetLevel]:
    """Get a dataset level by name."""
    return DATASET_LEVELS.get(level_name)


def list_levels() -> List[str]:
    """List all available dataset levels."""
    return sorted(DATASET_LEVELS.keys())


def get_level_config(level_name: str) -> Dict:
    """Get a flat config dict for a dataset level."""
    level = get_level(level_name)
    if not level:
        raise ValueError(f"Unknown dataset level: {level_name}")
    
    return {
        "name": level.name,
        "description": level.description,
        "enabled_groups": level.enabled_groups,
        "sequence_length": level.sequence_length,
        "forecast_horizon": level.forecast_horizon,
        "window_seconds": level.window_seconds,
        "window_step_seconds": level.window_step_seconds,
        "epochs": level.epochs,
        "batch_size": level.batch_size,
        "hidden_size": level.hidden_size,
        "num_layers": level.num_layers,
        "dropout": level.dropout,
        "learning_rate": level.learning_rate,
        "datasets": level.datasets,
        "target_metrics": level.target_metrics,
    }


def apply_level_to_config(level_name: str, base_config: Dict) -> Dict:
    """Apply a dataset level's settings to a base configuration dict."""
    level = get_level(level_name)
    if not level:
        raise ValueError(f"Unknown dataset level: {level_name}")
    
    config = base_config.copy()
    config.update({
        "sequence_length": level.sequence_length,
        "forecast_horizon": level.forecast_horizon,
        "window_size_seconds": level.window_seconds,
        "window_step_seconds": level.window_step_seconds,
        "model": {
            **config.get("model", {}),
            "hidden_size": level.hidden_size,
            "num_layers": level.num_layers,
            "dropout": level.dropout,
            "learning_rate": level.learning_rate,
            "epochs": level.epochs,
            "batch_size": level.batch_size,
        },
        "features": {
            group: group in level.enabled_groups or REGISTRY.groups.get(group, FeatureGroup("", "", [])).required
            for group in REGISTRY.get_canonical_group_order()
        },
    })
    return config