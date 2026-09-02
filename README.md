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
│   ├── models/                   ← base_model, lstm_world_model, linear_world_model,
│   │                                 trainer, baselines/
│   ├── forecasting/              ← attack_forecaster, stage_predictor, confidence
│   ├── counterfactual/           ← simulator, defensive_actions
│   ├── explainability/           ← shap_explainer
│   ├── mitre/                    ← attack_mapper
│   ├── graph/                    ← predictive_attack_graph
│   ├── evaluation/               ← metrics, baselines, unseen_attack
│   ├── ingestion/                ← parser, synthetic, datasets/adapters
│   └── dashboard/                ← 8-page Flask dashboard
├── tests/                        ← pytest (netwatch core + e2e)
├── data/                         ← runtime artifacts (gitignored)
├── configs/
├── docs/                         ← ARCHITECTURE.md, EXPERIMENTS.md, MODEL_CARD.md
├── run.py                        ← entry point
├── requirements.txt
└── (audit docs) PROJECT_AUDIT.md, REMOVED_COMPONENTS.md, FINAL_AUDIT.md
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- `torch` (CPU build is fine), `scikit-learn`, `flask`, `shap`, `numpy`

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

---

## Dashboard pages

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

---

## Example output

For every current state the system produces something like:

```
Current Risk: 42%        Stage: Reconnaissance

+1 window  → Initial Access     — 55%
+2 windows → Execution          — 67%
+3 windows → Lateral Movement   — 76%
+4 windows → Command and Control — 83%
+5 windows → Exfiltration       — 89%

Counterfactual defence:
   No Action      → 89%
   Block Source   → 24%
   Isolate Host   → 36%
   Restrict Port  → 41%

Recommended Action: Block Source
Reason: largest reduction in predicted future attack risk.
```

All probabilities are **actual model outputs** produced by feeding each action's
modified state through the World Model and reading its predicted risk trajectory.

---

## Tests

```bash
python -m pytest tests/ -v
```

Covers feature extraction, state construction, sequence generation, model
training/prediction, K-step rollout, counterfactual actions, risk comparison,
and dashboard routes.

---

## Documentation

- `docs/ARCHITECTURE.md` — technical architecture
- `docs/EXPERIMENTS.md` — evaluation methodology and honest results
- `docs/MODEL_CARD.md` — model details, capabilities, limitations
- `PROJECT_AUDIT.md` — pre-refactor audit
- `REMOVED_COMPONENTS.md` — what was removed and why
- `FINAL_AUDIT.md` — PS-requirement compliance checklist

---

## License

MIT License.
