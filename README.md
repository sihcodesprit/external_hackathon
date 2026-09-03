# 🛡️ SIH26153 — Counterfactual Cyber World Model

**Problem statement (SIH-26153):** AI Based Network Attack Forecasting from
Network Traffic Data

**Problem owner:** NTRO

**System:** An **AI-based Counterfactual Cyber World Model** for multi-step
network attack forecasting and proactive cyber-defence decision support.

---

## What is this?

Conventional intrusion detection answers *"what attack is happening now?"*. This
system goes further and acts as a **temporal Cyber World Model** that learns how
the network state evolves over time, then answers:

1. **What is happening now?** — the current `NetworkState` (S_t)
2. **What is likely to happen next?** — the learned transition `P(S_{t+1} | S_t)`
3. **What will the attack look like several steps from now?** — K-step forward simulation
4. **Why does the model think this?** — SHAP / explainability
5. **What happens if the defender does nothing?**
6. **What happens if the defender blocks / isolates / restricts something?**
7. **Which defensive action produces the safest predicted future?** — counterfactual simulation

The core is a genuine **LSTM World Model** (not a re-labelled classifier) that
consumes temporal sequences of network states and recursively generates future
states via `rollout()`. It is fully **offline** — no cloud or external inference.

---

## How it works (end-to-end)

```
Network traffic (synthetic / PCAP / CSV / flow records)
        │
        ▼
Flow + packet + temporal features  ──►  NetworkState S_t
        │
        ▼
Temporal sequences  [S(t-4) … S(t)]  ──►  S(t+1)
        │
        ▼
LSTM World Model  P(S_{t+1} | S_t)
        │
        ▼
K-step rollout  S_{t+1} → S_{t+2} → … → S_{t+K}
        │
        ▼
Per step:  attack probability · MITRE stage · confidence · top features
        │
        ▼
Predictive attack graph (current + predicted states)
        │
        ▼
Counterfactual simulation:
   no_action  block_source  block_dest_port  isolate_host  terminate_flow  restrict_path
        │            │               │               │              │             │
        └────────────┴───────────────┴───────────────┴──────────────┴─────────────┘
                                    │
                                    ▼
         compare predicted futures → recommend the action that minimises future risk
                                    │
                                    ▼
                            SHAP / XAI explanation
                                    │
                                    ▼
                              Flask dashboard
```

---

## Project structure

```
project/
├── netwatch/                     ← Counterfactual Cyber World Model
│   ├── config.py                 ← shared config, feature list, hyperparameters
│   ├── pipeline.py               ← end-to-end orchestrator
│   ├── features/                 ← network_state, sequences, flow/packet/temporal
│   │   ├── network_state.py      ← NetworkState dataclass and StateBuilder
│   │   ├── feature_registry.py   ← centralized feature configuration
│   │   ├── packet_features.py    ← packet-level features (TTL, payload, window, IAT)
│   │   ├── flow_features.py      ← bidirectional flow features
│   │   ├── tcp_features.py       ← TCP handshake / ghost ratio features
│   │   ├── entropy_features.py   ← Shannon entropy + temporal trajectories
│   │   ├── temporal_features.py  ← IAT stats, jitter, periodicity, burstiness, FFT
│   │   ├── graph_features.py     ← dynamic network graph topology
│   │   ├── trajectory_features.py← temporal derivatives (delta, acceleration)
│   │   ├── baseline_features.py  ← benign baseline deviation (z-score, percentile)
│   │   └── sequences.py          ← temporal sequence dataset construction
│   ├── models/                   ← base_model, lstm_world_model, linear_world_model,
│   │                                 trainer, baselines/
│   ├── forecasting/              ← attack_forecaster, stage_predictor, confidence
│   ├── counterfactual/           ← simulator, defensive_actions
│   ├── explainability/           ← shap_explainer
│   ├── mitre/                    ← attack_mapper
│   ├── graph/                    ← predictive_attack_graph
│   ├── evaluation/               ← metrics, baselines, unseen_attack, ablation
│   ├── ingestion/                ← parser, synthetic, datasets/adapters, dataset_levels
│   └── dashboard/                ← 9-page Flask dashboard
├── tests/                        ← pytest (netwatch core + e2e)
├── data/                         ← runtime artifacts (gitignored)
├── configs/                      ← config.yaml
├── docs/                         ← ARCHITECTURE.md, EXPERIMENTS.md, MODEL_CARD.md
├── run.py                        ← entry point
├── forecast.py                   ← CSV/JSONL forecast CLI
├── forecast_pcap.py              ← PCAP forecast CLI
├── requirements.txt
└── (audit docs) PROJECT_AUDIT.md, REMOVED_COMPONENTS.md, FINAL_AUDIT.md
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- `torch` (CPU build is fine), `scikit-learn`, `flask`, `shap`, `numpy`, `pyyaml`

### Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # macOS/Linux

pip install -r requirements.txt
copy .env.example .env         # Windows  (optional)
```

### Run

```bash
python run.py                  # train World Model + start dashboard
# Open http://localhost:5000
```

Other entry-point options:

```bash
python run.py --pipeline-only   # train + evaluate + forecast, print report, exit
python run.py --no-pipeline     # dashboard only (trains lazily on first request)
python run.py --port 8080
```

### Forecast from files

```bash
# From CSV/JSONL flow records
python forecast.py --input data.csv --horizon 5

# From PCAP packet capture
python forecast_pcap.py --input capture.pcap --horizon 5
```

---

## Dashboard pages (9)

| Page | Route | Content |
|---|---|---|
| Dashboard | `/dashboard` | Current risk + stage + latest forecast summary |
| 10-Min Radar | `/radar` | Future risk timeline |
| Attack Graph | `/graph` | Predictive attack graph (current + predicted) |
| Counterfactual | `/counterfactual` | What-if defence simulation + recommendation |
| Stages | `/stages` | Attack stage timeline + MITRE trajectory |
| Explainability | `/explainability` | SHAP / top contributing features |
| Evaluation | `/evaluation` | World Model vs baseline metrics |
| Scenarios | `/scenarios` | Ad-hoc scenario / data explorer |
| **Upload / Demo** | `/upload` / `/demo` | **PCAP/CSV upload, demo mode** |

---

## Features

### Network State Representation (S_t)
- **Traffic features**: packet_rate, byte_rate, flow_rate, connection_rate, total_packets, total_bytes, average_packet_size, packet_size_variance, flow_duration_mean
- **Packet features**: TTL, TTL variance, TCP window, window variance, IP fragmentation, payload size/distribution, packet size/distribution, IAT mean/variance/max, TCP retransmissions, TCP flags, protocol, ports
- **Flow features**: bidirectional packet/byte ratios, forward/backward packets/bytes, IAT stats
- **TCP handshake features**: SYN/SYN-ACK/ACK/RST/FIN counts, ratios (syn_ack_ratio, half_open_ratio), temporal derivatives
- **Entropy features**: Shannon entropy for ports, protocols, IPs, payload, packet size, TCP flags + temporal trajectories (ΔH, Δ²H)
- **Temporal features**: IAT mean/std/variance/CV/min/max, autocorrelation, periodicity, burstiness, FFT (optional)
- **Graph features**: node/edge count, density, degree stats, clustering, centrality, new edges/destinations, temporal deltas
- **Markov features**: TCP state transition probabilities
- **Trajectory features**: delta/acceleration for key variables
- **Baseline deviation**: z-scores, percentiles, absolute deviations from benign baseline

### World Model
- **Architecture**: LSTM (configurable: linear, transformer future)
- **Input**: sequence_length × n_features
- **Output**: predicted next state vector
- **K-step rollout**: recursive future state simulation

### Forecasting
- **Attack risk**: learned risk head (logistic regression) on predicted states
- **MITRE ATT&CK stage**: heuristic + classifier fallback
- **Confidence**: magnitude + stage prob + attack prob
- **Predictive attack graph**: nodes (stages) + edges (transitions)

### Counterfactual Simulation
- **Actions**: no_action, block_source, block_dest_port, isolate_host, terminate_flow, restrict_path
- **Mechanism**: modify state → rollout → risk head → compare trajectories
- **Recommendation**: minimizes predicted peak risk

### Explainability
- **SHAP**: on learned risk head
- **Fallback**: feature magnitude
- **Temporal**: when features changed

### Evaluation
- **Continuous**: MSE, RMSE, MAE, cosine similarity
- **Classification**: accuracy, precision, recall, F1, ROC-AUC
- **Forecasting**: Brier score, calibration, precision@horizon
- **Counterfactual**: risk reduction, stability, action ranking
- **Baselines**: Logistic Regression, Random Forest, Gradient Boosting
- **Unseen attack**: generalization to held-out stages
- **Ablation studies**: feature groups, graph, entropy, temporal, model vs baselines

---

## CLI Commands

### Training & Dashboard
```bash
python run.py                      # train + dashboard
python run.py --pipeline-only      # train + evaluate + forecast, exit
python run.py --no-pipeline        # dashboard only
python run.py --port 8080          # custom port
```

### Forecasting
```bash
# From CSV/JSONL
python forecast.py --input data.csv --horizon 5 --output result.json

# From PCAP
python forecast_pcap.py --input capture.pcap --horizon 5 --output result.json
```

### Tests
```bash
python -m pytest tests/ -v
```

---

## Documentation

- `docs/ARCHITECTURE.md` — technical architecture
- `docs/EXPERIMENTS.md` — evaluation methodology and honest results
- `docs/MODEL_CARD.md` — model details, capabilities, limitations
- `docs/HOW_TO_RUN.pdf` — step-by-step **How to Run** guide (regenerate with `python make_howto_pdf.py`)
- `PROJECT_AUDIT.md` — pre-refactor audit
- `REMOVED_COMPONENTS.md` — what was removed and why
- `FINAL_AUDIT.md` — PS-requirement compliance checklist

---

## Configuration

All configuration in `configs/config.yaml`:
- Window/sequence/forecast parameters
- Feature group toggles
- Model hyperparameters
- Counterfactual actions
- Ablation study configs
- Dashboard settings

Environment variables override defaults (see `.env.example`).

---

## Dataset Adapters

Supported datasets (adapters in `netwatch/ingestion/datasets/adapters.py`):
- CIC-IDS2017/2018
- CTU-13
- UNSW-NB15
- CICIoT2023

Dataset complexity levels (1-6) in `netwatch/ingestion/dataset_levels.py`.

---

## License

MIT License.