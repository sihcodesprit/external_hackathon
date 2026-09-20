# NetWatch — Codebase Summary

> Working notes captured after a full read-through of the repository. Use this as
> an orientation map and a backlog of known issues. Last updated on the `dev`
> branch.

---

## 1. What this is

**NetWatch / SIH-26153** — a *Counterfactual Cyber World Model* for multi-step
network attack forecasting and proactive cyber-defence decision support
(Smart India Hackathon problem statement, NTRO as problem owner).

Conventional IDS answers *"what attack is happening now?"*. This system learns
a temporal transition `P(S_{t+1} | S_t)` over windowed `NetworkState`s, then:

1. Reports the current state `S_t`.
2. Runs K-step recursive rollouts (`rollout()`) of a genuine **World Model**
   (LSTM or linear next-state regressor), not a re-labelled classifier.
3. Maps predicted behaviour onto MITRE ATT&CK stages/techniques.
4. Explains per-step contributions (SHAP / feature-magnitude fallback).
5. Simulates **counterfactual defensive actions** and recommends the safest one.
6. Cross-checks everything with an 8-engine ensemble verdict.

It is fully offline (no cloud / external inference) and trains on a per-capture,
in-memory basis in the dashboard.

---

## 2. High-level data flow

```
ingest (parser.PacketRecord  — PCAP / CSV / JSONL / synthetic / live normalizer)
  → EntityResolver + NetworkGraph        (IP entities, topology)
  → StateBuilder.build_states()          → List[NetworkState] (windowed features + label/stage)
  → assign_labels_and_stages()           (heuristic labels/stages when missing)
  → StateNormalizer.fit/transform()      → normalized feature vectors
  → build_sequences()                    → X (N, seq_len, n_feat), Y (N, n_feat) next-state
  → WorldModelTrainer.fit()              → WorldModel.fit()   (LSTM or Linear)
  → AttackForecaster                     (holds world model + normalizer + stage predictor + risk head)
      forecast()                         → K-step rollout → {risk, stage, confidence, features, ...}
  → CounterfactualEngine.simulate()      → per-action K-step risk trajectories → recommend()
  → build_predictive_graph() / AttackMapper / ShapExplainer+TemporalExplainer / EnsembleScorer
  → dashboard/analysis.build_document    → one canonical AnalysisDoc for every screen
```

---

## 3. Directory map

| Path | Responsibility |
|---|---|
| `run.py` | Entry point (loads `.env`, optional `--pipeline-only`, serves dashboard via waitress) |
| `netwatch/pipeline.py` | Top-level orchestrator: `load_data → train → evaluate → forecast_and_simulate → save_report` |
| `netwatch/config.py` | Shared config from `configs/config.yaml` + env overrides; builds the 132-column feature registry |
| `netwatch/core/` | `NetworkEvent` canonical event type; `schemas.py` dataclasses (currently unused in production) |
| `netwatch/features/` | 11 feature groups → `NetworkState`; `StateNormalizer`; sequence builders; feature registry |
| `netwatch/models/` | `WorldModel` ABC + `LSTMWorldModel` / `LinearWorldModel`, `WorldModelTrainer`, `ModelRegistry`, baseline classifiers |
| `netwatch/forecasting/` | `AttackForecaster` (K-step), `StagePredictor`, `confidence`, `EnsembleScorer` (8 detectors) |
| `netwatch/counterfactual/` | `CounterfactualEngine` + 6 `DefensiveAction`s (simulation-only mutations) |
| `netwatch/evaluation/` | Continuous/classification metrics, baselines, unseen-attack, ablation |
| `netwatch/explainability/` | `ShapExplainer` + `TemporalExplainer` |
| `netwatch/mitre/` | Stage → MITRE ATT&CK tactic/technique mapper |
| `netwatch/graph/` | Predictive attack graph builder (timeline + stage-collapsed) |
| `netwatch/network/` | Entity resolution, network graph, asset inventory |
| `netwatch/recommendations/` | `DefensiveRanker` (currently dead code) |
| `netwatch/live/` | TShark subprocess pipeline: locator → command → runner → sensor → flow tracker → window manager → state builder; URL monitor; SSE manager |
| `netwatch/dashboard/` | Flask app (all `/api/*`), async analysis jobs, canonical analysis registry, Model Test Center, synthetic scenarios |
| `frontend/` | React 18 + Vite + TS SPA (16 pages), served from `frontend/dist` |
| `tests/` | ~120 pytest unit tests (linear model patched in; no TShark needed) |
| `scripts/` | Cross-platform setup, TShark discovery/install/config, environment checks |
| `docs/` | README + this file + operational guides (see `docs/` index) |

---

## 4. Key components

### 4.1 Dashboard (`netwatch/dashboard/app.py`)

- Flask app serving the React SPA + JSON API. Every page reads the **same
  canonical analysis document** stored in the in-memory `_analyses` registry
  keyed by one `analysis_id` — re-uploading is never required.
- Async job manager (`/api/analyze`) with progress callbacks and a Model Test
  Center (`/api/model-test/jobs`) that runs each component and publishes the
  resulting document canonically.
- A background prewarm thread builds the zero-data pipeline at startup so the
  first page request never blocks behind heavy imports.
- Bundled model artifacts are **deleted at startup**
  (`_clean_predefined_artifacts`) so analysis is always driven by *user-uploaded*
  traffic, never a shipped dataset.

### 4.2 World models (`netwatch/models/`)

- `LSTMNextState` (Linear proj → 2-layer LSTM → MLP head) wrapped by
  `LSTMWorldModel`; `LinearWorldModel` is a ridge-regression baseline used by
  the live pipeline (fast refits).
- `rollout()` recursively feeds each predicted vector back through a sliding
  window.
- `WorldModelTrainer` does a temporal (no-shuffle) split and delegates to
  `model.fit()`.

### 4.3 Forecasting (`netwatch/forecasting/`)

- `AttackForecaster.forecast(history, k)` → K-step rollout with per-step risk
  (LR risk head or magnitude fallback), stage (heuristic rules with an
  exponential-decay probability distribution), confidence (deterministic
  weighted formula).
- `EnsembleScorer` runs 8 detectors (world model, RF, GBM, LR, entropy, TCP
  dynamics, graph, MITRE heuristic) to a weighted [0,100] consensus and a
  threat-level band + defence recommendation.

### 4.4 Counterfactual (`netwatch/counterfactual/`)

- `CounterfactualEngine.simulate(history, actions, k)` mutates the last
  `effect_window` (default 3) normalized vectors per action, rolls out each
  through the real world model, compares `peak_risk`, then `recommend()` picks
  the safest non-`no_action` (unless it doesn't beat doing nothing).
- Containment actions replace vectors with the trained `benign_profile`; if no
  risk head was trained, containment is a silent no-op.

### 4.5 Live monitoring (`netwatch/live/`)

- Single source of truth for TShark: `tshark_locator.py` (discovery/version/
  capabilities) → `tshark_command.py` (safe argv builder) → `tshark_runner.py`
  (Real/Mock) → `tshark_sensor.py` (subprocess manager).
- `live_pipeline.py` is the hub: EK-lines → `PacketRecord` → `WindowManager`
  (30 s window / 5 s step) → `FlowTracker` → `StateBuilder` → refit linear
  model every 3 windows → `AttackForecaster` → SSE push.
- URL Monitor: DNS-resolve a target URL, derive a host filter, and report
  destination-observed traffic metrics.

### 4.6 Features (`netwatch/features/`)

- Registry-driven; 11 toggleable groups (traffic, packet, flow, tcp_handshake,
  entropy, temporal, graph, markov, trajectory, baseline_deviation, spectral).
- `NetworkState.vector()` zero-fills any registered column the feature modules
  don't actually produce (see known issues).

---

## 5. Environment / deployment

- Python ≥3.10; `requirements.txt` (Flask, waitress, numpy, sklearn, torch,
  shap, scapy, psutil, pytest).
- TShark required only for live capture; auto-discovered (env → PATH →
  platform candidates → setup script install).
- `run.py` → waitress server (`NETWATCH_THREADS`, default 16).
- Docker multi-stage (`base`/`development`/`live-capture`/`production`);
  compose profiles `dev`, `live`, `pipeline`, `prod`. `Procfile` for Heroku.
- CI: unit tests (py3.10/3.11/3.12), ruff + mypy, `npm run build`, Docker
  builds, TShark integration job.

---

## 6. Known issues / backlog

### 6.1 Broken imports & dead code

- **`netwatch/ingestion/datasets/adapters.py` has a `SyntaxError`** (duplicate
  `src_ip=` kwarg in `CTU13Adapter`) — any `netwatch.ingestion.datasets.*`
  import crashes, so CTU-13/CIC ingestion is dead.
- `netwatch/recommendations/defensive_ranker.py` (`DefensiveRanker`) is **never
  imported** — ranking logic is duplicated in `simulator.recommend()` and
  `EnsembleScorer`.
- `netwatch/core/schemas.py` dataclasses (`ForecastStep`, `EntityInfo`,
  `EdgeInfo`) are unused and have drifted from the real dict shapes.
- `StagePredictor.train()` result is never consumed; `predict_proba()` builds a
  15-feature `vec` that is never used.
- `config.CONFIDENCE_WEIGHTS` is not wired into `confidence.py` (hardcoded
  0.5/0.3/0.2 split). (`risk_alpha` is likewise unused.)

### 6.2 Feature vocabulary mismatch (recurring bug source)

- Stage predictor, defensive actions, confidence, and ensemble fallbacks assume
  the **legacy 15-feature vocabulary** (`payload_mean`, `packets_per_second`,
  ...) while the registry-driven world model uses the 132-column registry
  (`payload_size_mean`, `packet_rate`, ...).
- `attack_forecaster._STAGE_FEATURE_ALIASES` papers over this for stage
  prediction only; defensive actions and ensemble fallbacks have no equivalent.
- Many registered columns are **never produced by any feature module** (markov
  probs, `degree_delta`, `centrality_delta`, `*_entropy_delta`, fwd/bwd flow
  fields) — `NetworkState.vector()` zero-fills them, so the model trains on
  constant-zero inputs.
- **Duplicate registry columns**: `iat_mean` ×3, `iat_variance` ×3, `iat_max`
  ×3, `packet_size_variance` ×2, `src_port`/`dst_port` ×2,
  `port_entropy_delta`/`acceleration` ×2 — inflate `N_FEATURES` and create
  correlated duplicated inputs.

### 6.3 Non-functional ablation

- `config.get_feature_registry()` rebuilds a fresh registry from YAML on every
  call and `NetworkState.vector()` calls `config.get_feature_columns()` again —
  so toggling a group on a local registry instance never changes what the
  normalizer/sequences/model actually see. Feature-group ablation is inert.

### 6.4 Model bugs

- **`LSTMWorldModel.load()` doesn't rebuild the optimizer** — calling `fit()`
  after `load()` silently trains a dead network; the optimizer is never
  saved/restored. `load()` also force-sets `is_trained=True`.
- `LinearWorldModel` doesn't clip predictions → can leave ~[-1,1] range.
- Trainer default `n_features=15` no longer matches the registry-driven count.
- `Pipeline()` and `load_pretrained()` **seed `results["evaluation"]` with
  hardcoded metrics** (mse 0.0124, acc 0.965/0.971/0.923) that look like
  fabricated results despite the "no fabricated numbers" claim.
- Risk-head fallback constant `/8` is duplicated in `attack_forecaster`,
  `evaluation/metrics`, and `confidence.py`'s `/10`.

### 6.5 Live / ingestion quirks

- `live/tshark_command.py` **inverts the promiscuous flag** (promiscuous=True
  emits `-p`, which *disables* promiscuity).
- `live/live_state.to_analysis_dict()` returns early — the `live_url` branch is
  unreachable and would raise `NameError` (`doc` undefined). URL-mode analysis
  docs omit URL/target data.
- `UrlTarget.last_resolved_at` never set → `ip_history` always `None`; DNS
  refresh updates the target IP set but **not the running TShark BPF** (rotated
  IPs missed until restart).
- `parser.load_pcap` is IPv4-only; IPv6-only captures raise "none had an IP
  layer".
- `flags_to_string` sorts flag chars alphabetically (parser: `"SA"` → `"AS"`),
  inconsistent with live's `tcp.flags.str` order.
- `baseline_features` uses `next(iter(set))` (nondeterministic min-samples
  probe); `tcp_features.syn_ack_ratio` degrades to a bare `syn` count when
  `ack == 0`.

### 6.6 Counterfactual

- Containment actions are no-ops when the risk head was never trained
  (`benign_profile is None` → `_neutralize` returns the vector unchanged).
- `recommend()` fabricates a synthetic "no_action" result if it wasn't part of
  the simulated actions and the best action has no risk reduction.
- Default `ACTIONS` in `defensive_actions.py` uses the legacy 15-column list —
  if applied to registry-column vectors, mutations become no-ops.

### 6.7 Frontend

- `ForecastTimeline` computes the current risk from an object as if it were a
  number → **NaN** current bar (offline `forecast.current` is an object).
- Backend never adds `confidence` to the current step → Confidence card shows
  "—" for offline analyses.
- `LiveMonitor` navigates to a non-existent `/live/:id` route (catch-all
  redirects home); the SSE `onmessage` handler is dead (only named `update`
  events fire); `events` state never populated.
- `SystemInfo` type missing `platform`/`feature_count` (build untyped so tsc
  doesn't catch it); `System.tsx` hardcodes **132** features, `ThreatHeader`
  hardcodes **8** detectors.
- `Card.pad` prop is a no-op; ~14 dead `api.*` methods, 3 dead hooks/util
  groups, 6 dead UI exports; stale/duplicated types
  (`ForecastStep`/`ForecastBlock`, two `ReportDocument`s, `state_groups`
  typed as record but actually an array).

### 6.8 Config / docs / deployment drift

- **Missing files referenced elsewhere**: `docs/ARCHITECTURE.md` (set as
  `pyproject.toml` `readme` — broken metadata), `docs/EXPERIMENTS.md`,
  `docs/MODEL_CARD.md`, `forecast.py`, `forecast_pcap.py` (README +
  clean-machine-checklist reference them; removed in commit `647cc4eb`).
- `pyproject.toml` build backend is non-standard
  (`setuptools.backends._legacy:_Backend`); `pip install -e .` would likely
  fail.
- **`tshark_integration` pytest mark is unregistered and unused** — the CI job
  selects zero tests; docs promise TShark integration tests that don't exist.
- `.env.example` uses `LIVE_*` keys but code only reads `NETWATCH_LIVE_*` /
  `TSHARK_PATH` — copied `.env` values are silently ignored.
- `netwatch/live/config.py` reads **only env vars**; the `live:` YAML block is
  ignored (divergent second config source).
- `config.yaml` `window_step_seconds: 10` (offline) vs `live.step_size: 5`.
- `model.yaml`, `network.yaml`, `scenarios.yaml` configs are unreferenced by
  code (only `assets.yaml` is loaded).
- **Docker images never build the frontend** (`production` copies only
  `netwatch/`, `data/`, `run.py`, ...) yet healthchecks hit the SPA route →
  containers would be flagged unhealthy / headless. CI Docker smoke test
  doesn't exercise the SPA path.
- `ModelRegistry.CHECKPOINTS_DIR` writes to `project_root/models/checkpoints`
  while `Pipeline.train()` persists to `data/models` — split locations.

---

## 7. Suggested focus areas

1. **Feature registry ↔ module reconcile** (`feature_registry.py` +
   `network_state.py`): remove duplicates, drop never-produced columns, fix
   vocab aliases. This is the model input contract; fixing it cascades to every
   downstream model/forecaster/evaluator.
2. **Fix the import-breaking adapters SyntaxError** if CTU-13/CIC ingestion is
   in scope.
3. **Ablation**: make feature-group toggles actually affect `vector()` /
   `build_sequences` (shared/mutable registry or explicit columns).
4. **LSTM load/fine-tune**: rebuild the optimizer on `load()`, persist
   optimizer state.
5. **Live URL analysis doc** + promiscuous-flag inversion + DNS→BPF refresh.
6. **Frontend data-shape fixes** (NaN timeline, confidence, route, types).
7. **Docs/deployment reconciliation** (missing doc files, `forecast*.py` CLIs,
   Docker SPA build, `pyproject.toml`, `.env.example`, lint markers).