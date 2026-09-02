# Setup Guide — SIH26153 Counterfactual Cyber World Model

This guide covers installation, the quick-start, and how to run the offline
World Model dashboard. It replaces the earlier detection/monitoring setup that
was removed during the refactor (see `REMOVED_COMPONENTS.md`).

> A printable step-by-step guide is also available at `docs/HOW_TO_RUN.pdf`
> (regenerate with `python make_howto_pdf.py`).

---

## 1. Prerequisites

- **Python 3.10+** (tested on 3.13)
- `pip`
- Optional: `git`

No cloud account, external API, or Npcap are required for the core system — it
runs fully **offline** on synthetic data by default, and can ingest PCAP / CSV /
flow data if you provide scapy.

---

## 2. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # macOS/Linux

pip install -r requirements.txt
```

`requirements.txt` installs `flask`, `gunicorn`, `numpy`, `scikit-learn`,
`torch`, `shap`, and `pytest`.

> **Optional — PCAP ingestion:** `pip install scapy` if you want to ingest
> `.pcap` files (used only when you call `netwatch.ingestion.parser.load_pcap`).

---

## 3. Run the dashboard

```bash
python run.py
# Open http://localhost:5000
```

On first request the Flask app lazily trains the LSTM World Model on synthetic
data and caches it for the process lifetime.

### Other run modes

| Command | Description |
|---|---|
| `python run.py` | Train World Model then start dashboard |
| `python run.py --pipeline-only` | Train + evaluate + forecast, print JSON report, exit |
| `python run.py --no-pipeline` | Dashboard only (trains lazily) |
| `python run.py --port 8080` | Serve on a specific port |

---

## 4. Environment variables (optional)

Copy `.env.example` to `.env` to customise:

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `5000` | Web server port |
| `FLASK_DEBUG` | `0` | Enable Flask debug / hot reload |
| `NW_WORLD_MODEL` | `lstm` | `lstm` or `linear` |
| `NW_EPOCHS` | `30` | Training epochs |
| `NW_EXPLAIN` | `1` | Enable SHAP explainability |

---

## 5. Run the tests

```bash
python -m pytest tests/ -v
```

The suite trains small World Models on tiny traces, so it stays fast, and
verifies the dashboard routes return HTTP 200.

---

## 6. Ingesting your own data (future work)

Dataset adapters already exist in `netwatch/ingestion/datasets/adapters.py` for
**CIC-IDS2017/2018, CTU-13, UNSW-NB15, and CICIoT2023**. They convert each
source schema into the common `PacketRecord` / `NetworkState` schema. No dataset
files ship with this repo; supplying real files and re-running the pipeline will
produce dataset-generalisation results (see `docs/EXPERIMENTS.md`).
