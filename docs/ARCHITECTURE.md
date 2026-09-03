# Architecture — Counterfactual Cyber World Model (SIH-26153)

This document describes the architecture of the upgraded SIH26153 system: an
**AI-based Counterfactual Cyber World Model** for multi-step network attack
forecasting and proactive cyber-defence decision support.

This supersedes the previous detection-centric architecture. See
`PROJECT_AUDIT.md` and `REMOVED_COMPONENTS.md` for the audit and removal log.

---

## 1. Design goals

- **Temporal, not static.** The system models the *evolution* of the network
  state, `P(S_{t+1} | S_t)`, rather than only classifying a single window.
- **Genuine World Model.** The core predictor consumes temporal sequences and
  generates future network-state vectors (K-step rollout). It is **not** a
  re-labelled Gradient Boosting classifier.
- **Counterfactual defence.** For a given threat, the system simulates
  alternative defensive actions and recommends the one that most reduces
  predicted future risk — all via actual model rollouts.
- **Offline.** No cloud API, no external inference, no remote prediction. All
  trained models are loaded locally.

---

## 2. High-level data flow

```
Network traffic (synthetic / PCAP / CSV / flow)
   │  netwatch.ingestion.parser.ingest()
   ▼
PacketRecord list
   │  netwatch.features.network_state.StateBuilder
   ▼
Windows of NetworkState  S_t  (flow + packet + temporal features)
   │  netwatch.features.sequences.StateNormalizer / build_sequences
   ▼
Temporal sequences  [S(t-L) … S(t)]  →  S(t+1)
   │  netwatch.models.lstm_world_model.LSTMWorldModel
   ▼
Learned  P(S_{t+1} | S_t)
   │  rollout()
   ▼
K predicted future states
   │  netwatch.forecasting.attack_forecaster + stage_predictor + confidence
   ▼
Per step: risk · stage · confidence · top features
   │  netwatch.graph.predictive_attack_graph
   ▼
Predictive attack graph (current + predicted)
   │  netwatch.counterfactual.simulator.CounterfactualEngine
   ▼
Per-action K-step rollouts → compare → recommended action
   │  netwatch.explainability.shap_explainer
   ▼
Explanation  →  netwatch.dashboard.app  (Flask, 9 pages)
```

---

## 3. Core components

### 3.1 NetworkState (`netwatch/features/network_state.py`)

Each time window is a `NetworkState` containing:

- **Traffic features:** `total_packets`, `total_bytes`, `packet_rate`, `byte_rate`,
  `flow_rate`, `connection_rate`, `average_packet_size`, `packet_size_variance`,
  `flow_duration_mean`
- **Packet features:** `ttl_mean`, `ttl_variance`, `tcp_window_mean`,
  `tcp_window_variance`, `ip_fragmentation_count`, `payload_size_mean`,
  `payload_size_variance`, `packet_size_mean`, `packet_size_variance`,
  `iat_mean`, `iat_variance`, `iat_max`, `tcp_retransmissions`,
  `protocol_tcp/udp/icmp`, `src_port`, `dst_port`
- **Flow features:** `src_ip`, `dst_ip`, `src_port`, `dst_port`, `protocol`,
  `tcp_flags`, `bytes`, `packets`, `duration`, `iat_mean/variance/max`,
  `fwd/bwd_packets`, `fwd/bwd_bytes`, `bidirectional_packet/byte_ratio`
- **TCP handshake features:** `syn_count`, `syn_ack_count`, `ack_count`,
  `rst_count`, `fin_count`, `syn_ack_ratio`, `syn_synack_ratio`,
  `rst_syn_ratio`, `half_open_ratio`, `ack_completion_ratio`,
  `delta_syn_rate`, `delta_syn_ack_ratio`, `delta_half_open_ratio`, `delta_rst_rate`
- **Entropy features:** `src/dst_port_entropy`, `protocol_entropy`,
  `src/dst_ip_entropy`, `payload/packet_size_entropy`, `tcp_flag_entropy`,
  plus temporal trajectories: `_delta`, `_acceleration` for each
- **Temporal features:** `iat_mean`, `iat_std`, `iat_variance`, `iat_cv`,
  `iat_min`, `iat_max`, `iat_autocorr`, `periodicity_score`, `burstiness`,
  `fft_dominant_freq`, `fft_spectral_power`
- **Graph features:** `node_count`, `edge_count`, `graph_density`,
  `average_degree`, `degree_variance`, `clustering_coefficient`,
  `new/removed_edges`, `new_destinations/sources`, centrality measures,
  `new_edges/destinations_rate`, temporal deltas
- **Markov features:** `p_synack_given_syn`, `p_rst_given_syn`,
  `p_ack_given_synack`, `p_fin_given_ack`, `p_rst_given_ack`,
  `p_timeout_given_syn`
- **Trajectory features:** `_delta`, `_acceleration` for key variables
  (`syn_rate`, `port_entropy`, `graph_density`, `packet_rate`, etc.)
- **Baseline deviation features:** `_zscore`, `_percentile`, `_deviation`
  for key variables against benign baseline

`StateBuilder` slides a window over timestamped packet records (optionally
grouped per source/destination pair) to produce a time-ordered list of states.
`compute_window_features` aggregates raw packet records into the feature vector.

### 3.2 Feature Registry (`netwatch/features/feature_registry.py`)

Centralized feature configuration avoiding hard-coded feature counts:

- `FeatureGroup`: logical groups (traffic, packet, flow, tcp_handshake,
  entropy, temporal, graph, markov, trajectory, baseline_deviation)
- `FeatureRegistry`: manages enabled/disabled groups, canonical order
- `build_registry_from_config()`: creates registry from config.yaml
- `get_feature_columns()`: returns flat list of enabled features
- Dynamic feature selection via configuration

### 3.3 Temporal sequence dataset (`netwatch/features/sequences.py`)

- `StateNormalizer` fits mean/std on training states and standardizes vectors.
- `build_sequences` builds supervised pairs
  `[S(t-L) … S(t)] → S(t+1)` (configurable `sequence_length`, `horizon`).
- `temporal_split` performs a **temporal / session-aware split** (first chunk
  trains, last chunk validates) to prevent data leakage.
- `assign_labels_and_stages` attaches a binary attack label and MITRE stage to
  each state (ground truth when available, else a documented heuristic).
- `split_by_group`: split by attacker IP or attack session for unseen-attack eval.

### 3.4 World Model interface (`netwatch/models/base_model.py`)

```python
class WorldModel(ABC):
    def fit(self, X, Y, **kwargs) -> dict: ...
    def predict_next_state(self, history): ...     # P(S_{t+1} | history)
    def rollout(self, history, k: int): ...        # recursively predict k states
    def save(self, path): ...
    def load(self, path) -> bool: ...
```

`WorldModelFactory` creates a concrete model by name (`lstm`, `linear`), so a
**Transformer / Temporal Transformer / Temporal GNN** can later be dropped in
without rewriting the pipeline.

### 3.5 LSTM World Model (`netwatch/models/lstm_world_model.py`)

```
history [seq_len x n_feat]
   → Linear projection
   → stacked LSTM
   → dense latent state
   → Linear next-state head (n_feat)
```

`rollout(history, k)` feeds each predicted state back as the new last timestep,
so future states are genuinely generated from previous predicted states rather
than a repeated probability.

### 3.6 Attack forecaster (`netwatch/forecasting/attack_forecaster.py`)

- Runs a K-step rollout from a history window.
- Applies a **learned risk head** (logistic regression fit on labelled states)
  to each predicted state to get future attack probability.
- Runs the **stage predictor** on each predicted state for the MITRE stage.
- Produces `current` + `future` steps, each with `risk`, `stage`,
  `stage_probability`, `confidence`, and supporting features.

### 3.7 Stage predictor & confidence (`netwatch/forecasting/`)

- `stage_predictor.py` predicts a kill-chain / MITRE stage with a stage
  probability and supporting features (heuristic for synthetic; a classifier
  can be plugged in with real labels).
- `confidence.py` estimates confidence from predicted-state magnitude, stage
  probability, and attack probability — deterministic, never fabricated.

### 3.8 MITRE mapper (`netwatch/mitre/attack_mapper.py`)

Maps a predicted stage to a MITRE ATT&CK tactic + representative technique
(e.g. `Exfiltration → T1048`). Returns `UNKNOWN` when evidence is insufficient.

### 3.9 Predictive attack graph (`netwatch/graph/predictive_attack_graph.py`)

Builds a directed graph of predicted stage transitions. Nodes carry severity,
risk, and stage; edges carry the predicted probability / confidence from the
rollout. Represents both the **current** state and the **predicted future**.

### 3.10 Counterfactual engine (`netwatch/counterfactual/`)

- `defensive_actions.py` defines simulation-only actions: `no_action`,
  `block_source`, `block_dest_port`, `isolate_host`, `terminate_flow`,
  `restrict_path`. Each mutates a state vector to represent the defender's
  intervention. **No real network changes are made.**
- `simulator.py` (`CounterfactualEngine`) for each action: modifies the recent
  history, runs a K-step rollout, computes the resulting risk trajectory via the
  learned risk head, and reports `final_risk` / `peak_risk`.
- `recommend()` selects the action that most reduces predicted near-term (peak)
  risk relative to `no_action`.

### 3.11 Explainability (`netwatch/explainability/shap_explainer.py`)

Uses SHAP on the learned risk head to produce the top contributing features for
each forecast. Falls back to a transparent feature-magnitude explanation when
SHAP is unavailable or no risk head is trained.

### 3.12 Evaluation (`netwatch/evaluation/`)

- `metrics.py` — continuous metrics (MSE/RMSE/MAE/cosine) on next-state
  prediction, plus classification metrics (accuracy/precision/recall/F1/ROC-AUC)
  from risk projection.
- `baselines.py` — Logistic Regression / Random Forest / Gradient Boosting
  baselines on flattened window features, compared against the World Model.
- `unseen_attack.py` — generalization test on an attack pattern withheld from
  training.
- `ablation.py` — AblationStudy framework for:
  - Feature ablation (progressive feature groups)
  - Graph ablation (with/without graph features)
  - Entropy ablation (without/with/temporal entropy)
  - Temporal ablation (raw/IAT/full temporal)
  - Model vs baselines comparison

### 3.13 Pipeline (`netwatch/pipeline.py`)

`Pipeline` orchestrates: load data → build states → temporal split → train World
Model → fit risk head → evaluate (+ baselines + unseen + ablation) → K-step
forecast → predictive graph → counterfactual simulation → SHAP → save report.

### 3.14 Dashboard (`netwatch/dashboard/app.py`)

9 server-rendered Flask pages (dashboard, radar, attack graph, counterfactual,
stages, explainability, evaluation, scenarios, upload/demo) plus JSON API
endpoints.

---

## 4. Ingestion & datasets

- `netwatch/ingestion/parser.py` — JSONL / PCAP (via scapy) / CSV / flow
  ingestion into normalized `PacketRecord`s.
- `netwatch/ingestion/synthetic.py` — self-contained synthetic traffic generator
  (development / demo / tests only).
- `netwatch/ingestion/datasets/adapters.py` — adapters for **CIC-IDS2017/2018,
  CTU-13, UNSW-NB15, CICIoT2023** converting each source into the common schema.
- `netwatch/ingestion/dataset_levels.py` — Dataset complexity levels (1-6):
  Level 1 (traffic only) → Level 6 (all features)

### Dataset Levels

| Level | Name | Feature Groups | Purpose |
|-------|------|---------------|---------|
| 1 | Basic | traffic | Sanity check |
| 2 | Packet | traffic + packet | Header features |
| 3 | Entropy | + entropy | Randomness detection |
| 4 | Temporal | + temporal | Jitter/periodicity |
| 5 | Graph | + graph | Topology |
| 6 | Full | all | Production |

---

## 5. Configuration (`configs/config.yaml`)

All paths, hyperparameters, feature columns, and flags in one YAML file:

- Window/sequence/forecast parameters
- Feature group toggles (all 10 groups)
- Model hyperparameters (hidden_size, num_layers, dropout, lr, etc.)
- Counterfactual actions and containment semantics
- Ablation study configurations
- Dashboard settings
- Environment variable overrides (`NW_WORLD_MODEL`, `NW_EPOCHS`, `NW_EXPLAIN`, `PORT`, `FLASK_DEBUG`)

Runtime config loaded via `netwatch.config` with YAML + env var support.

---

## 6. Offline guarantee

- Models: `data/models/world_model_lstm.pt`, `feature_scaler.pkl` — loaded
  locally.
- No HTTP calls, no cloud SDK, no external inference in the prediction path.

---

## 7. CLI Commands

- `python run.py` — train + dashboard
- `python run.py --pipeline-only` — train + evaluate + forecast + report
- `python run.py --no-pipeline` — dashboard only (lazy train)
- `python forecast.py --input data.csv --horizon 5` — CSV/JSONL forecast
- `python forecast_pcap.py --input capture.pcap --horizon 5` — PCAP forecast
- `python -m pytest tests/` — run test suite (61 tests)
- `python make_howto_pdf.py` — regenerate HOW_TO_RUN.pdf