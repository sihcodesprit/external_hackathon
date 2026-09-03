"""
Shared configuration for the Counterfactual Cyber World Model.

All paths, hyperparameters, and runtime feature flags live here. 
Loads from configs/config.yaml with environment variable overrides.
Nothing here depends on external submodules.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# ── Paths ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / "configs" / "config.yaml"

# Load YAML config
def _load_yaml_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}

_YAML_CONFIG = _load_yaml_config()


def _get(path: str, default: Any = None) -> Any:
    """Get nested config value using dot notation (e.g., 'model.hidden_size')."""
    keys = path.split(".")
    val = _YAML_CONFIG
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        else:
            return default
    return val


def _env_override(key: str, default: Any) -> Any:
    """Check environment variable, fall back to default."""
    env_val = os.getenv(key)
    if env_val is not None:
        # Try to parse as appropriate type
        if isinstance(default, bool):
            return env_val.lower() in ("1", "true", "yes", "on")
        if isinstance(default, int):
            return int(env_val)
        if isinstance(default, float):
            return float(env_val)
        if isinstance(default, list):
            return [v.strip() for v in env_val.split(",")]
        return env_val
    return default


# ── Paths ──────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / _get("paths.data_dir", "data")
GENERATED_DIR = DATA_DIR / _get("paths.generated_dir", "generated")
MODEL_DIR = DATA_DIR / _get("paths.model_dir", "models")
REPORTS_DIR = DATA_DIR / _get("paths.reports_dir", "reports")
CONFIG_DIR = PROJECT_ROOT / _get("paths.config_dir", "configs")
ARTIFACTS_DIR = PROJECT_ROOT / _get("paths.artifacts_dir", "artifacts")

# Intermediate outputs
PACKETS_FILE = GENERATED_DIR / "packets.jsonl"
STATES_FILE = GENERATED_DIR / "network_states.jsonl"
SEQUENCES_FILE = GENERATED_DIR / "sequences.npz"

# Model artifacts
WORLD_MODEL_PATH = MODEL_DIR / "world_model_lstm.pt"
STAGE_MODEL_PATH = MODEL_DIR / "stage_predictor.pt"
SCALER_PATH = MODEL_DIR / "feature_scaler.pkl"

# ── Ingestion ──────────────────────────────────────────────
DEFAULT_INGEST_MODE = _env_override("NW_INGEST", _get("ingest.default_mode", "synthetic"))
PCAP_MAX_PACKETS = _get("ingest.pcap_max_packets", 100000)
CSV_CHUNK_SIZE = _get("ingest.csv_chunk_size", 10000)

# ── Feature engineering ────────────────────────────────────
WINDOW_SECONDS = _get("window_size_seconds", 30)
WINDOW_STEP_SECONDS = _get("window_step_seconds", 10)
SEQUENCE_LENGTH = _get("sequence_length", 10)
ANONYMIZE_IPS = _get("anonymize_ips", False)

# Feature group toggles
FEATURE_GROUPS = _get("features", {
    "traffic": True,
    "packet": True,
    "flow": True,
    "tcp_handshake": True,
    "entropy": True,
    "temporal": True,
    "graph": True,
    "markov": True,
    "trajectory": True,
    "baseline_deviation": True,
    "spectral": False,
})

# ── World Model ────────────────────────────────────────────
WORLD_MODEL_TYPE = _env_override("NW_WORLD_MODEL", _get("model.type", "lstm"))
HIDDEN_SIZE = _get("model.hidden_size", 128)
NUM_LAYERS = _get("model.num_layers", 2)
DROPOUT = _get("model.dropout", 0.2)
LEARNING_RATE = _get("model.learning_rate", 1e-3)
BATCH_SIZE = _get("model.batch_size", 64)
NUM_EPOCHS = _env_override("NW_EPOCHS", _get("model.epochs", 50))
TRAIN_VAL_SPLIT = _get("model.train_val_split", 0.2)
DEVICE = _get("model.device", "auto")

# ── Forecasting ────────────────────────────────────────────
K_STEP_HORIZON = _get("forecasting.k_step_horizon", 5)
ESCALATION_THRESHOLD = _get("forecasting.escalation_threshold", 0.5)
RISK_ALPHA = _get("forecasting.risk_alpha", 0.0)
CONFIDENCE_WEIGHTS = _get("forecasting.confidence_weights", {
    "magnitude": 0.5,
    "stage_prob": 0.3,
    "attack_prob": 0.2,
})

# ── Counterfactual ────────────────────────────────────────
DEFAULT_ACTIONS = _get("counterfactual.default_actions", [
    "no_action", "block_source", "block_dest_port",
    "isolate_host", "terminate_flow", "restrict_path"
])
CONTAINMENT_ACTIONS = _get("counterfactual.containment_actions", [
    "block_source", "block_dest_port", "isolate_host",
    "terminate_flow", "restrict_path"
])
EFFECT_WINDOW = _get("counterfactual.effect_window", 3)
RECOMMENDATION_METRIC = _get("counterfactual.recommendation_metric", "peak_risk")

# ── Explainability ────────────────────────────────────────
ENABLE_EXPLAINABILITY = _env_override("NW_EXPLAIN", _get("explainability.enable_shap", True))
SHAP_FALLBACK = _get("explainability.fallback_to_magnitude", True)
MAX_DISPLAY_FEATURES = _get("explainability.max_display_features", 10)

# ── MITRE ──────────────────────────────────────────────────
MITRE_STAGE_TO_TACTIC = _get("mitre.stage_to_tactic", {
    "Reconnaissance": "Discovery",
    "Initial Access": "Initial Access",
    "Execution": "Execution",
    "Lateral Movement": "Lateral Movement",
    "Command and Control": "Command and Control",
    "Exfiltration": "Exfiltration",
    "Impact": "Impact",
})

# ── Evaluation ────────────────────────────────────────────
BASELINE_MODELS = _get("evaluation.baseline_models", [
    "logistic_regression", "random_forest", "gradient_boosting"
])
UNSEEN_ATTACK_ENABLED = _get("evaluation.unseen_attack.enabled", True)
UNSEEN_HOLDOUT_STAGES = _get("evaluation.unseen_attack.holdout_stages", [
    "Exfiltration", "Impact"
])

# ── Ablation ──────────────────────────────────────────────
ABLATION_ENABLED = _get("ablation.enabled", True)
ABLATION_FEATURE_SETS = _get("ablation.feature_sets", [])
ABLATION_TYPES = _get("ablation.ablation_types", ["graph", "entropy", "temporal", "model_vs_baselines"])

# ── Dashboard ──────────────────────────────────────────────
DASHBOARD_HOST = _get("dashboard.host", "0.0.0.0")
DASHBOARD_PORT = _env_override("PORT", _get("dashboard.port", 5000))
DASHBOARD_DEBUG = _env_override("FLASK_DEBUG", _get("dashboard.debug", False))
AUTO_TRAIN_ON_START = _get("dashboard.auto_train_on_start", True)
DEMO_MODE = _get("dashboard.demo_mode", True)

# ── Runtime flags ──────────────────────────────────────────
ENABLE_SHAP = ENABLE_EXPLAINABILITY


# ── Feature Registry Integration ──────────────────────────
def get_feature_registry():
    """Get feature registry built from config."""
    from netwatch.features.feature_registry import build_registry_from_config
    return build_registry_from_config(_YAML_CONFIG)


def get_feature_columns() -> List[str]:
    """Get the flat list of enabled feature columns from registry."""
    registry = get_feature_registry()
    return registry.get_enabled_features()


def get_n_features() -> int:
    """Get the number of enabled features."""
    return len(get_feature_columns())


# For backward compatibility
FEATURE_COLUMNS = get_feature_columns()
N_FEATURES = get_n_features()


def ensure_dirs():
    for d in [DATA_DIR, GENERATED_DIR, MODEL_DIR, REPORTS_DIR, CONFIG_DIR, ARTIFACTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def get_config_summary() -> Dict[str, Any]:
    """Return a summary of current configuration for logging/debugging."""
    return {
        "model_type": WORLD_MODEL_TYPE,
        "window_seconds": WINDOW_SECONDS,
        "sequence_length": SEQUENCE_LENGTH,
        "k_step_horizon": K_STEP_HORIZON,
        "n_features": N_FEATURES,
        "feature_groups": {k: v for k, v in FEATURE_GROUPS.items() if v},
        "device": DEVICE,
        "epochs": NUM_EPOCHS,
        "batch_size": BATCH_SIZE,
    }