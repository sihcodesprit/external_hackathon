"""
Shared configuration for the Counterfactual Cyber World Model.

All paths, hyperparameters, and runtime feature flags live here. Env vars may
override the defaults. Nothing here depends on external submodules.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
GENERATED_DIR = DATA_DIR / "generated"
MODEL_DIR = DATA_DIR / "models"
REPORTS_DIR = DATA_DIR / "reports"
CONFIG_DIR = PROJECT_ROOT / "configs"

# Intermediate outputs
PACKETS_FILE = DATA_DIR / "generated" / "packets.jsonl"
STATES_FILE = DATA_DIR / "generated" / "network_states.jsonl"
SEQUENCES_FILE = DATA_DIR / "generated" / "sequences.npz"

# Model artifacts
WORLD_MODEL_PATH = MODEL_DIR / "world_model_lstm.pt"
STAGE_MODEL_PATH = MODEL_DIR / "stage_predictor.pt"
SCALER_PATH = MODEL_DIR / "feature_scaler.pkl"

# ── Ingestion ──────────────────────────────────────────────
DEFAULT_INGEST_MODE = os.getenv("NW_INGEST", "synthetic")  # synthetic | pcap | csv

# ── Feature engineering ────────────────────────────────────
WINDOW_SECONDS = 30          # aggregation window per NetworkState
WINDOW_STEP_SECONDS = 10     # step between consecutive windows
SEQUENCE_LENGTH = 10         # number of past states fed to the world model

# ── World Model ────────────────────────────────────────────
WORLD_MODEL_TYPE = os.getenv("NW_WORLD_MODEL", "lstm")
HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2
LEARNING_RATE = 1e-3
BATCH_SIZE = 32
NUM_EPOCHS = int(os.getenv("NW_EPOCHS", "30"))
TRAIN_VAL_SPLIT = 0.2

# ── Forecasting ────────────────────────────────────────────
K_STEP_HORIZON = 5           # default rollout horizon
ESCALATION_THRESHOLD = 0.5
RISK_ALPHA = 0.0             # not used; risk computed directly from model

# ── Counterfactual ────────────────────────────────────────
DEFAULT_ACTIONS = ["no_action", "block_source", "block_dest_port",
                   "isolate_host", "terminate_flow", "restrict_path"]

# ── Runtime flags ──────────────────────────────────────────
ENABLE_EXPLAINABILITY = os.getenv("NW_EXPLAIN", "1") == "1"

FEATURE_COLUMNS = [
    # flow
    "bytes", "packets",
    # packet
    "ttl_mean", "payload_mean", "payload_max", "tcp_window_mean",
    # temporal
    "packets_per_second", "connection_rate", "unique_dst_ports",
    "unique_dst_hosts", "syn_rate", "ack_rate", "rst_rate", "syn_ack_ratio",
    "port_entropy",
]
N_FEATURES = len(FEATURE_COLUMNS)


def ensure_dirs():
    for d in [DATA_DIR, GENERATED_DIR, MODEL_DIR, REPORTS_DIR, CONFIG_DIR]:
        d.mkdir(parents=True, exist_ok=True)
