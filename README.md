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

## 🚀 Quick Start

### One-Command Setup (Recommended)

The project includes a **cross-platform bootstrap system** that automatically
installs Python dependencies, discovers/installs TShark, and configures everything.

```bash
# Linux / macOS
git clone <REPO_URL>
cd <PROJECT>
chmod +x scripts/setup_linux.sh
./scripts/setup_linux.sh

# Windows PowerShell
git clone <REPO_URL>
cd <PROJECT>
.\scripts\setup_windows.ps1

# Cross-platform (Python)
python scripts/setup.py
```

### Verify Installation

```bash
python scripts/check_tshark.py
```

Expected when TShark is ready:

```
========================================
CYBER WORLD MODEL ENVIRONMENT CHECK
========================================

Operating System:
  Linux 6.8.0 (x86_64)

Python:
  3.11.9 (CPython)

TShark:
  AVAILABLE

TShark Path:
  /usr/bin/tshark

TShark Version:
  4.2.3

Live Capture:
  READY

Available Interfaces:
  ● eth0 (192.168.1.42)
  ● wlan0 (10.0.0.5)

========================================
SETUP COMPLETE
========================================
```

### Run the Dashboard

```bash
python run.py
# Open http://localhost:5000
```

| Page | URL | Purpose |
|------|-----|---------|
| **Live Monitor** | `/live` | Real-time packet capture → World Model forecasting |
| **URL Monitor** | `/url-monitor` | Enter URL → DNS resolve → observe destination traffic |
| **System** | `/system` | Runtime, models, artifacts, **TShark dependency status** |
| Dashboard | `/dashboard` | Risk overview + network topology |
| Forecast | `/forecast` | K-step risk timeline |
| Attack Graph | `/graph` | Predictive attack graph (current + predicted) |
| Counterfactual | `/counterfactual` | What-if defence simulation |
| Stages | `/stages` | MITRE ATT&CK progression |
| Explainability | `/explainability` | SHAP / top features |
| Evaluation | `/evaluation` | World Model vs baselines |
| Scenarios | `/scenarios` | Synthetic demos |
| Upload | `/upload` | PCAP/CSV upload + analysis |

---

## 📁 Project Structure

```
project/
├── netwatch/                     ← Counterfactual Cyber World Model
│   ├── config.py                 ← Shared config, feature list, hyperparameters
│   ├── pipeline.py               ← End-to-end orchestrator
│   ├── features/                 ← NetworkState, sequences, flow/packet/temporal
│   ├── models/                   ← LSTM/Linear World Model, trainer, baselines
│   ├── forecasting/              ← Attack forecaster, stage predictor, confidence
│   ├── counterfactual/           ← Simulator, defensive actions
│   ├── explainability/           ← SHAP explainer
│   ├── mitre/                    ← MITRE ATT&CK mapper
│   ├── graph/                    ← Predictive attack graph
│   ├── evaluation/               ← Metrics, baselines, unseen attack, ablation
│   ├── ingestion/                ← Parser, synthetic, dataset adapters
│   ├── live/                     ← **TShark live monitoring pipeline**
│   │   ├── tshark_locator.py     ← Single source of truth: discovery/version/capabilities
│   │   ├── tshark_command.py     ← Safe TShark command builder
│   │   ├── tshark_runner.py      ← Runner interface (Real/Mock for tests)
│   │   ├── tshark_sensor.py      ← Subprocess manager
│   │   ├── health.py             ← Health check (compat layer over locator)
│   │   ├── interface.py          ← Cross-platform interface discovery
│   │   ├── url_monitor.py        ← URL-target traffic metrics
│   │   ├── url_target.py         ← URL resolution + BPF filter building
│   │   ├── live_pipeline.py      ← Window manager + flow tracker + state builder
│   │   └── manager.py            ← Session control + SSE
│   └── dashboard/                ← 14-page Flask dashboard + React SPA
├── scripts/                      ← **Bootstrap & verification**
│   ├── setup.py                  ← Cross-platform orchestrator
│   ├── setup_windows.ps1         ← Windows one-command setup
│   ├── setup_linux.sh            ← Linux/macOS one-command setup
│   ├── check_tshark.py           ← Full environment verification
│   ├── find_tshark.py            ← Print TShark path
│   ├── configure_tshark.py       ← Write TSHARK_PATH to .env
│   └── _setup_common.py          ← Shared utilities
├── tests/                        ← Pytest (unit + integration)
├── docs/                         ← Architecture, requirements, troubleshooting
├── frontend/                     ← React + TypeScript + Vite SPA
├── data/                         ← Runtime artifacts (gitignored)
├── configs/                      ← config.yaml
├── run.py                        ← Entry point (loads .env, starts server)
├── forecast.py                   ← CSV/JSONL forecast CLI
├── forecast_pcap.py              ← PCAP forecast CLI
├── requirements.txt              ← Python dependencies only
├── .env.example                  ← Environment template
├── .gitignore
├── Dockerfile                    ← Multi-stage (dev / live-capture / prod)
├── docker-compose.yml            ← Dev / live / pipeline / prod profiles
├── pyproject.toml                ← Build + pytest + ruff + mypy config
└── README.md                     ← This file
```

---

## 🔧 Configuration

All configuration in `configs/config.yaml` (see file for full list). Key sections:

- **Ingestion**: PCAP/CSV/JSONL modes, chunk sizes
- **Feature Engineering**: Window/step/sequence, 11 feature group toggles
- **World Model**: LSTM/Linear, hidden size, layers, dropout, LR, epochs
- **Forecasting**: K-step horizon, escalation threshold, confidence weights
- **Counterfactual**: 6 defensive actions, effect window, recommendation metric
- **Live Monitoring (TShark)**: All `live.*` settings (see below)

### Environment Variables (`.env`)

Copy `.env.example` to `.env` and customise. The `run.py` entry point loads it.

```bash
# TShark / Live Monitoring
TSHARK_PATH=                    # Explicit path (empty = auto-discover)
NETWATCH_LIVE_ENABLED=true      # Master kill-switch
LIVE_WINDOW_SIZE=30             # Seconds per aggregation window
LIVE_STEP_SIZE=5                # Seconds between window starts
LIVE_FORECAST_HORIZON=5         # K-step rollout

# Flask
FLASK_SECRET_KEY=change-me
PORT=5000
```

### TShark Executable Resolution Priority

1. `TSHARK_PATH` env var (explicit)
2. `NETWATCH_TSHARK_PATH` env var (legacy)
3. `tshark` on `PATH`
4. Platform candidates (Program Files, `/usr/bin`, `/usr/local/bin`, Homebrew, etc.)
5. Setup script installation

---

## 🐳 Docker

### Development (no live capture)
```bash
docker compose up dev
# http://localhost:5000
```

### Live Capture (Linux host only)
```bash
docker compose --profile live up live
# Uses host network + NET_RAW/NET_ADMIN caps
```

### Production
```bash
docker compose up prod
# Gunicorn, non-root user, healthchecks
```

**Note:** On Docker Desktop (macOS/Windows), `network_mode: host` doesn't expose host interfaces. Run natively or in a Linux VM for live capture.

---

## 🧪 Testing

```bash
# Unit tests (no TShark required — uses MockTsharkRunner)
python -m pytest tests/ -v -m "not integration and not tshark_integration"

# TShark integration tests (requires TShark + capture permission)
TSHARK_INTEGRATION_TESTS=1 python -m pytest tests/ -m tshark_integration -v

# Lint & type check
ruff check netwatch scripts tests
mypy --ignore-missing-imports netwatch/live/tshark_locator.py netwatch/live/tshark_command.py netwatch/live/tshark_runner.py
```

### CI/CD (GitHub Actions)

- **Unit tests**: Ubuntu, Python 3.10/3.11/3.12
- **Lint**: `ruff` + `mypy`
- **Frontend**: `npm run build`
- **Docker**: builds `dev`, `live-capture`, `prod` targets
- **TShark integration**: runs only when `TSHARK_INTEGRATION_TESTS` secret is set

---

## 📚 Documentation

| File | Description |
|------|-------------|
| `docs/ARCHITECTURE.md` | Technical architecture |
| `docs/EXPERIMENTS.md` | Evaluation methodology & results |
| `docs/MODEL_CARD.md` | Model details, capabilities, limitations |
| `docs/system-requirements.md` | **System-level dependencies (TShark, permissions, etc.)** |
| `docs/troubleshooting.md` | Common issues & solutions |
| `docs/live-tshark-monitoring.md` | Live pipeline architecture & API |
| `docs/clean-machine-checklist.md` | Fresh-machine verification steps |

---

## 🔒 Security

- **No `shell=True`** — all subprocess calls use list arguments
- **Interface validation** — restricted to `[A-Za-z0-9_.-]`
- **BPF filter validation** — internally generated, length-capped
- **URL validation** — only `http`/`https`; hostname regex; SSRF protection
- **No secrets in repo** — `.env` gitignored, `.env.example` has placeholders
- **Capture privileges documented separately** — app runs as normal user

---

## 📦 Requirements

### Python (≥ 3.10)
All in `requirements.txt`:
```
flask>=3.0,<4
gunicorn>=21.0
werkzeug>=3.0
numpy>=1.26
scikit-learn>=1.4
torch>=2.1
pyyaml>=6.0
shap>=0.46
scapy>=2.5      # PCAP ingestion
psutil>=5.9     # Interface discovery (optional)
pytest>=7.4     # Testing
```

### System (Live Capture Only)
| Platform | Package |
|----------|---------|
| Debian/Ubuntu/Kali | `tshark` |
| Fedora/RHEL | `wireshark-cli` |
| Arch | `wireshark-cli` |
| openSUSE | `wireshark` |
| macOS | `wireshark` (Homebrew) |
| Windows | `WiresharkFoundation.Wireshark` (winget) |

---

## 🛠️ Development

### Frontend
```bash
cd frontend
npm install
npm run dev      # Dev server (HMR) at http://localhost:5173
npm run build    # Production build to frontend/dist/
```

The Flask app serves `frontend/dist/` in production.

### Adding Tests
- Unit tests: `tests/test_*.py` (no TShark, use `MockTsharkRunner`)
- Integration tests: mark with `@pytest.mark.tshark_integration`

---

## 📄 License

MIT License.

---

## 🙏 Acknowledgements

- **NTRO** — Problem owner (SIH-26153)
- **Wireshark Foundation** — TShark packet capture engine
- **PyTorch / scikit-learn / SHAP** — ML stack