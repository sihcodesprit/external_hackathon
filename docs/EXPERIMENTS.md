# Experiments — SIH26153 Counterfactual Cyber World Model

This document records the evaluation methodology and **honest** results. All
numbers were produced by actually running the code on the current synthetic
dataset. Where real datasets are required and are not present, the result is
explicitly stated as **"Not evaluated yet"** — nothing is fabricated.

---

## 1. Dataset

- **Source:** `netwatch/ingestion/synthetic.py` (development / demo / testing
  only).
- **Setup:** 4 traces, 120-minute each, staggered in time, 30s aggregation
  windows with 10s step, 15 flow/packet/temporal features per state.
- **Ground truth:** each window is labelled attack/benign and assigned a MITRE
  stage (`Reconnaissance → Initial Access → Execution → Lateral Movement →
  Command and Control → Exfiltration`).
- **Split:** temporal / session-aware (first 80% train, last 20% validate) —
  no random row-level leakage.

> **Limitation:** this is synthetic data. It is used to demonstrate the
> end-to-end World Model, forecast, counterfactual, and evaluation *pipeline*,
> not as evidence of real-world performance. Real-dataset results remain **Not
> evaluated yet** until CIC-IDS / CTU-13 / UNSW-NB15 / CICIoT data is supplied
> (adapters are provided).

---

## 2. World Model vs Baselines (synthetic test split)

Run parameters: 4 traces, seed 42, LSTM (2 layers, hidden 64), 30 epochs.
`n_train = 2294` sequences, `n_test = 566` sequences.

### 2.1 World Model — continuous next-state prediction

| Metric | Value |
|---|---|
| MSE | 0.112 |
| RMSE | 0.335 |
| MAE | 0.162 |
| Mean cosine similarity | 0.870 |

### 2.2 World Model — risk-projected attack classification

The risk head (logistic regression) was applied to predicted states and
thresholded at 0.5:

| Metric | Value |
|---|---|
| Accuracy | 0.991 |
| Precision | 1.000 |
| Recall | 0.962 |
| F1 | 0.981 |
| ROC-AUC | 0.985 |

### 2.3 Baselines (classical classifiers, flattened windows)

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|
| Logistic Regression | 0.996 | 1.000 | 0.985 | 0.992 | 0.996 |
| Random Forest | 0.996 | 1.000 | 0.985 | 0.992 | 0.989 |

> The baselines are strong on this synthetic set because the synthetic attack
> windows are cleanly separable. The World Model's purpose is not to beat them
> on point-in-time classification — it is to forecast **future** states, which
> static classifiers cannot do.

---

## 3. Unseen-attack generalization (synthetic)

Attack stages `Exfiltration` / `Impact` were **withheld entirely from training**;
the World Model was evaluated on those unseen sequences.
`n_unseen = 1257`.

| Metric | Value |
|---|---|
| MSE (continuous) | 0.271 |
| RMSE | 0.521 |
| MAE | 0.245 |
| Mean cosine | 0.747 |
| Accuracy (risk-projected) | 0.928 |
| Precision | 1.000 |
| Recall | 0.341 |
| F1 | 0.508 |
| ROC-AUC | 0.898 |

> **Interpretation:** the World Model shows reasonable generalization (high
> precision, high AUC) to an unseen attack stage, but lower recall — it tends
> to under-predict the unseen stage. This is expected for a held-out technique
> on synthetic data and is reported honestly.

---

## 4. K-step forecast and counterfactual (example run)

From `run.py --pipeline-only` (and the dashboard):

- Current state and per-step `risk` / `stage` are produced by the learned model.
- Counterfactual example: with the risk head trained, the recommended action
  was **`block_source`** with a meaningful reduction in predicted near-term
  (peak) risk. The exact percentages vary per run and data — the dashboard
  always shows the live computed values.

**No fixed-percentage discounts are used.** Each action modifies the state, the
World Model performs a K-step rollout, and the risk head reads the resulting
trajectory.

---

## 5. Real-dataset status

| Dataset | Adapter | Data present | Result |
|---|---|---|---|
| CIC-IDS2017/2018 | `CICIDSAdapter` | No file shipped | **Not evaluated yet** |
| CTU-13 | `CTU13Adapter` | No file shipped | **Not evaluated yet** |
| UNSW-NB15 | `UNSWNB15Adapter` | No file shipped | **Not evaluated yet** |
| CICIoT2023 | `CICIoTAdapter` | No file shipped | **Not evaluated yet** |

To evaluate on a real dataset, drop the file into `data/`, load it through the
matching adapter, and re-run the pipeline. The pipeline is dataset-agnostic.

---

## 6. How to reproduce

```bash
pip install -r requirements.txt
python run.py --pipeline-only          # trains + evaluates + forecasts + report
python -m pytest tests/ -v             # unit + e2e tests
```
