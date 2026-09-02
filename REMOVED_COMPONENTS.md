# REMOVED COMPONENTS

Every component removed during the upgrade to the Counterfactual Cyber World
Model, with the reason and replacement. **Nothing was deleted without first
verifying dependencies.**

---

## Stack A — removed old detection stack (`integration/**`)

| Component | Reason | Replacement | Impact |
|---|---|---|---|
| `integration/app.py` | Old Flask dashboard for detection pipeline | `netwatch/dashboard/app.py` | None — new 8-page dashboard replaces it |
| `integration/config.py` | Config for old pipeline (empty-repo paths) | `netwatch/config.py` | None |
| `integration/pipeline_runner.py` | Orchestrator importing empty `repos/` | `netwatch/pipeline.py` | None — old was non-runnable |
| `integration/detection_engine.py` | Heuristic IDS tied to empty `repos/` | `netwatch/features/sequences.py` label assignment | None |
| `integration/model_forecaster.py` | **Model B** (Gradient Boosting escalation) | `netwatch/models/lstm_world_model.py` | Replaced by genuine temporal World Model |
| `integration/forecast_features.py` | Duplicate feature extraction | `netwatch/features/network_state.py` | Consolidated |
| `integration/killchain_adapter.py` | Old kill-chain → MITRE adapter | `netwatch/mitre/attack_mapper.py` | Consolidated |
| `integration/packet_capture.py` | Live capture | `netwatch/ingestion/parser.py` (PCAP) | PCAP ingestion preserved; live capture not required for offline World Model |
| `integration/live_processor.py` | Real-time monitor | removed | Not part of World Model scope |
| `integration/prevention.py` | Auto-block firewall rules | removed | Simulation-only design; no real network changes |
| `integration/ratelimit.py`, `validation.py`, `logging_config.py` | Old API infra | removed | Old API removed |
| `integration/requirements.txt` | Duplicate deps | `requirements.txt` (root) | Consolidated |

## Stack B — removed static frontend (`frontend/**`)

| Component | Reason | Replacement | Impact |
|---|---|---|---|
| Vercel React static app, `proxy.js`, `main.js`, CSS, `DEPLOY.md` | Duplicate dashboard outside the Python app | `netwatch/dashboard/` (Flask server-rendered) | None — the 8-page Flask dashboard is the single UI |

## Stack C — removed empty placeholder repos (`repos/**`)

| Component | Reason | Replacement | Impact |
|---|---|---|---|
| `repos/Network-Threat-Anomaly-Visualizer/` etc. | Empty placeholder dirs; not git submodules | `netwatch/` is self-contained | None — removed the broken dependency |

## Stack D — removed root helper scripts

| Component | Reason | Replacement | Impact |
|---|---|---|---|
| `keep_awake.py` | Render keep-alive pinger (cloud host, not offline) | none | Offline design needs no keep-alive |
| `validate_detection.py` | Depend on `integration.detection_engine` + empty repos | none | Obsolete IDS validation |
| `scan_self.py` | Hardcoded-IP demo scanner for old dashboard | none | Demo-only, old dashboard |
| `simulate_attack.py` | Depends on `integration.app` | none | Obsolete |
| `jsonl_to_iptables.py` | Generates iptables from old anomaly files | none | Conflict: simulation-only design, no real blocking |

## Stack E — removed old deployment assets

| Component | Reason | Replacement | Impact |
|---|---|---|---|
| `Procfile` | `gunicorn integration.app:app` | rewritten → `netwatch.dashboard.app:app` | None |
| `Dockerfile` | `COPY integration/`, `COPY repos/`, `CMD integration.app` | rewritten for netwatch | None |
| `docker-compose.yml` | Old dev/prod/pipeline services | rewritten | None |
| `.env.example` | Old feature flags | rewritten | None |

## Stack F — removed old documentation / API spec

| Component | Reason | Replacement | Impact |
|---|---|---|---|
| `docs/openapi.yaml` | Describes old integration API | none (API retired) | None |
| `docs/DEMO_SCRIPT.md` | Old end-to-end demo (integration) | `netwatch` demo in README | None |
| `docs/RESULTS.md` | Claims metrics for old Model A/B | `EXPERIMENTS.md` (real results) | None |

## Stack G — removed obsolete tests

Old integration tests referenced `integration.*` / `frontend` / `repos` and
would fail after the stack was removed.

| Test | Reason |
|---|---|
| `test_app.py` | tests old Flask app |
| `test_config.py` | tests `integration.config` |
| `test_detection_engine.py` | tests `integration.detection_engine` |
| `test_forecast_features.py` | tests old feature extractor |
| `test_integration_e2e.py` | end-to-end old pipeline |
| `test_logging_config.py` | old logging |
| `test_model_forecaster.py` | old Model B |
| `test_pipeline_runner.py` | old orchestrator |
| `test_ratelimit.py` | old rate limiting |
| `test_run.py` | old CLI |
| `test_validation.py` | old IDS validation |
| `test_deployment.py` | Vercel frontend deployment |
| `test_keepalive.py` | Render keep-alive |
| `test_docs.py` | old docs check |
| `test_docker.py` | old Dockerfile checks |
| `tests/conftest.py` | bootstrapped empty `repos/` paths |

Kept: `tests/test_netwatch_core.py` — the netwatch World Model tests.

## Stack H — removed runtime/data cruft

| Component | Reason |
|---|---|
| `.pytest_cache/` | generated |
| all `__pycache__/` | generated bytecode |
