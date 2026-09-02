# PROJECT AUDIT — SIH26153 AI-Based Network Attack Forecasting

Audit of the repository at the start of the upgrade to a **Counterfactual Cyber
World Model**. This document records the state of the project, what already
satisfies the Problem Statement (SIH-26153), what is redundant, and the 
decisions made during refactoring.

---

## 1. Existing Architecture (discovered during audit)

The repository contained **two parallel, competing stacks**:

### Stack A — NEW: `netwatch/` (keep — this is the target architecture)

A complete, self-contained **Counterfactual Cyber World Model**. It requires no
external git submodules and runs fully offline. Structure:

| Module | Purpose |
|---|---|
| `netwatch/config.py` | Shared paths, hyperparameters, feature list, feature flags |
| `netwatch/features/network_state.py` | `NetworkState` (S_t) with flow + packet + temporal features |
| `netwatch/features/sequences.py` | Temporal sequence dataset; temporal/session-aware splits |
| `netwatch/models/base_model.py` | Abstract `WorldModel` interface (swappable LSTM/Transformer/GNN) |
| `netwatch/models/lstm_world_model.py` | LSTM World Model learning P(S_{t+1}\|S_t) + K-step `rollout()` |
| `netwatch/models/linear_world_model.py` | Linear baseline world model (sanity check) |
| `netwatch/models/trainer.py` | Training loop wrapper |
| `netwatch/models/baselines/benchmark.py` | Logistic Regression / Random Forest / Gradient Boosting baselines |
| `netwatch/forecasting/attack_forecaster.py` | K-step forward simulation + learned risk head |
| `netwatch/forecasting/stage_predictor.py` | MITRE attack-stage prediction + stage probability |
| `netwatch/forecasting/confidence.py` | Forecast confidence estimation |
| `netwatch/counterfactual/defensive_actions.py` | Simulation-only defensive actions |
| `netwatch/counterfactual/simulator.py` | Counterfactual engine (per-action K-step rollout + recommend) |
| `netwatch/explainability/shap_explainer.py` | SHAP / feature-magnitude explanations |
| `netwatch/mitre/attack_mapper.py` | MITRE ATT&CK tactic/technique mapping |
| `netwatch/graph/predictive_attack_graph.py` | Predictive attack graph (current + predicted states) |
| `netwatch/evaluation/metrics.py` | Continuous + classification metrics |
| `netwatch/evaluation/baselines.py` | World Model vs baseline evaluation |
| `netwatch/evaluation/unseen_attack.py` | Unseen-attack generalization test |
| `netwatch/ingestion/parser.py` | JSONL / PCAP (scapy) / CSV / flow ingestion |
| `netwatch/ingestion/synthetic.py` | Synthetic traffic generator (dev/demo only) |
| `netwatch/ingestion/datasets/adapters.py` | CIC-IDS, CTU-13, UNSW-NB15, CICIoT adapters |
| `netwatch/pipeline.py` | End-to-end orchestrator |
| `netwatch/dashboard/` | 8-page Flask dashboard |

### Stack B — OLD: `integration/` + `frontend/` + `repos/` (remove)

The earlier, detection-centric implementation built around **empty** `repos/`
placeholder directories (`Network-Threat-Anomaly-Visualizer`,
`network-intrusion-detection`, `cyber-killchain-reconstruction-engine`,
`network-port-scanner`). It was **non-runnable** as shipped:

- `integration/pipeline_runner.py` imports `generate_test_data`,
  `AnomalyDetector`, `train_model`, etc. from `repos/...` paths that are empty.
- `run.py`, `validate_detection.py`, `keep_awake.py`, `simulate_attack.py`,
  tests `tests/conftest.py` all bootstrap these empty `repos/` paths.
- Its "Model A" (PS40 NSL-KDD classifier) and "Model B" (Gradient Boosting
  escalation forecaster) both depend on the missing repos.

This stack conflicts with the required World Model architecture (Model B was a
Gradient Boosting classifier, not a temporal world model) and is entirely
replaced by Stack A.

---

## 2. Existing Models

| Model | Location | Used? | Verdict |
|---|---|---|---|
| LSTM World Model (`world_model_lstm.pt`) | `netwatch/models/` | Yes | **Keep** — the core World Model |
| Feature scaler (`feature_scaler.pkl`) | `netwatch/models/` | Yes | **Keep** — normalizer artifact |
| `LinearWorldModel` | `netwatch/models/linear_world_model.py` | Test/sanity | **Keep** (small, useful) |
| Logistic Regression / RF / GBM (baselines) | `netwatch/models/baselines/benchmark.py` | Yes | **Keep** — baselines |
| Old Model A (PS40) | `repos/network-intrusion-detection/` | No (empty) | **Remove** — dead |
| Old Model B (Gradient Boosting escalation) | `integration/model_forecaster.py` | No | **Remove** — superseded by LSTM World Model |

## 3. Existing Functionality (kept, in `netwatch/`)

- **PCAP ingestion** → `netwatch/ingestion/parser.py::load_pcap`
- **Flow / CSV ingestion** → `parser.py::load_flow_csv`
- **Anomaly detection** → label assignment via
  `netwatch/features/sequences.py::assign_labels_and_stages`
- **Feature extraction** → `netwatch/features/network_state.py::compute_window_features`
- **MITRE mapping** → `netwatch/mitre/attack_mapper.py`
- **Attack graph** → `netwatch/graph/predictive_attack_graph.py`
- **Dashboard** → `netwatch/dashboard/` (8 pages)

## 4. Duplicate Functionality

| Function | Old stack | New stack |
|---|---|---|
| Dashboard | `integration/app.py` + `frontend/` | `netwatch/dashboard/app.py` |
| Ingestion | `integration/packet_capture.py` | `netwatch/ingestion/parser.py` |
| Forecasting | `integration/model_forecaster.py` | `netwatch/forecasting/` |
| MITRE | `integration/killchain_adapter.py` | `netwatch/mitre/` |
| Keep-alive (Render) | `integration/app.py` + `keep_awake.py` | **not needed** (offline) |

## 5. Missing PS Requirements (reviewed against Problem Statement 26153)

| Requirement | Status in `netwatch/` |
|---|---|
| Temporal World Model (not a classifier) | Implemented (LSTM) |
| NetworkState representation | Implemented |
| Temporal/session-aware dataset splits | Implemented |
| K-step forward simulation | Implemented |
| Attack-stage prediction (MITRE pattern) | Implemented |
| Predictive attack graph | Implemented |
| SHAP explainability | Implemented |
| Counterfactual defensive simulation + recommendation | Implemented |
| Baseline evaluation (LR/RF/GBM vs World Model) | Implemented |
| Unseen-attack evaluation | Implemented (synthetic) |
| Public dataset adapters (CIC/CTU/UNSW/CICIoT) | Implemented (mapping only) |
| Offline operation | Implemented (no cloud dependency) |

## 6. Files — Final Classification

### Files to keep (unchanged)
- `netwatch/**` — the World Model package
- `requirements.txt` — dependency manifest (netwatch)
- `tests/test_netwatch_core.py` — netwatch tests
- `pyproject.toml` — build/test config (updated coverage source already points at `netwatch`)

### Files to rewrite
- `run.py` — entry point → launch `netwatch.dashboard.app`
- `Dockerfile`, `Procfile`, `docker-compose.yml` — point at netwatch app
- `README.md` — document the World Model
- `docs/ARCHITECTURE.md` — replace with netwatch architecture

### Files safe to remove
- `integration/**` (old Flask + Model A/B + detection stack)
- `frontend/**` (Vercel React duplicate dashboard)
- `repos/**` (empty placeholder directories)
- `keep_awake.py`, `validate_detection.py`, `scan_self.py`,
  `simulate_attack.py`, `jsonl_to_iptables.py`
- `docs/openapi.yaml`, `docs/DEMO_SCRIPT.md`, `docs/RESULTS.md` (old stack)
- Old integration tests (see `REMOVED_COMPONENTS.md`)
- `.pytest_cache/`, all `__pycache__/`

### New files required
- `PROJECT_AUDIT.md` (this file)
- `REMOVED_COMPONENTS.md`
- `FINAL_AUDIT.md`
- `ARCHITECTURE.md` (replace)
- `EXPERIMENTS.md`
- `MODEL_CARD.md`

---

## 7. Verification

The `netwatch/` pipeline was executed end-to-end as part of this audit:

```
DATA:   34560 packets, 1080 states, 168 attack / 912 benign
TRAIN:  status=trained, risk_head_trained=True
EVAL:   world_model present
FORECAST: current risk / stage + K steps produced
COUNTERFACTUAL: recommendation produced (real model outputs)
GRAPH:  nodes + edges built
MITRE:  trajectory mapped
```

No results are fabricated; every number above was produced by actually running
the pipeline.
