"""
Flask dashboard — SOC-style interface for the Counterfactual Cyber World Model.

Serves the React SPA + JSON API:
  1. SOC Overview (risk overview + network topology)
  2. Analyze PCAP (ZIP discovery + real-time analysis progress)
  3. Network State (windowed feature timeline)
  4. Forecast View (K-step risk timeline)
  5. Attack Graph (predicted stage transitions)
  6. MITRE ATT&CK progression
  7. Explainability (SHAP + temporal)
  8. Counterfactual Lab (defensive action simulation)
  9. Model Test Center (test each component separately)
 10. Evaluation
 11. Scenarios (clearly-labelled synthetic demos)
 12. System
 13. Analysis History
 14. Report Export
"""

import functools
import gzip
import json
import logging
import os
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename

from flask import Flask, jsonify, request, send_from_directory, abort

from netwatch import __version__
from netwatch.config import DASHBOARD_DEBUG, DASHBOARD_PORT, DASHBOARD_HOST
from netwatch.ingestion.parser import ingest
from netwatch.pipeline import Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _configure_file_logging() -> None:
    """Mirror ERROR-level logs (incl. tracebacks) to netwatch_server.log."""
    try:
        from logging.handlers import RotatingFileHandler

        log_path = Path(__file__).resolve().parent.parent.parent / "netwatch_server.log"
        handler = RotatingFileHandler(
            str(log_path), maxBytes=2_000_000, backupCount=2, encoding="utf-8")
        handler.setLevel(logging.ERROR)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger()
        if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
            root.addHandler(handler)
    except Exception:  # logging must never break the app
        pass


_configure_file_logging()

_pipeline_cache = {}
_pipeline_lock = threading.Lock()

ALLOWED_EXTENSIONS = {".pcap", ".pcapng", ".csv", ".jsonl", ".zip"}
MAX_FILE_SIZE = int(os.environ.get("NETWATCH_MAX_UPLOAD_MB", "1024")) * 1024 * 1024

# ── Async analysis job manager ────────────────────────────────────────────
_jobs = {}
_jobs_lock = threading.Lock()
_jobs_history = []          # summary entries for the Analysis History screen
_jobs_history_lock = threading.Lock()

# ── Model Test Center job registry (owned by the backend so runs survive
# navigation and browser refresh) ──────────────────────────────────────────
_model_test_jobs = {}
_model_test_jobs_lock = threading.Lock()

# ── Canonical analysis registry ───────────────────────────────────────────
# Every completed analysis (from /api/analyze, scenarios, legacy /api/upload
# OR a finished Model Test Center "Run All Modules" pass) is stored here under
# ONE analysis_id. That id is the single source of truth for every screen:
# Overview, Network Status, Forecast, Attack Graph, MITRE, Explainability and
# Counterfactual all read the same persisted document.
_analyses = {}
_analyses_lock = threading.Lock()
_active_analysis_id = None
_active_analysis_lock = threading.Lock()

# Lazy background prewarm so the first page request never blocks
# behind the (heavy) pipeline load: assets and health answer instantly.
_PREWARM_STARTED = False


def _ensure_prewarm() -> None:
    global _PREWARM_STARTED
    if _PREWARM_STARTED:
        return
    if os.environ.get("NETWATCH_SKIP_PREWARM") == "1":
        return
    _PREWARM_STARTED = True

    def _preload_heavy_modules() -> None:
        """Import heavy request-time modules up-front so the first interaction
        (page load, analysis run, live capture) never blocks on imports."""
        try:
            from netwatch.live import interface, manager, health as _live_health  # noqa: F401
        except Exception as e:  # noqa: BLE001
            logger.warning("Live monitoring preload failed: %s", e)
        try:
            from netwatch.dashboard import analysis as _analysis  # noqa: F401
            from netwatch.dashboard.synthetic import scenario_manifest  # noqa: F401
        except Exception as e:  # noqa: BLE001
            logger.warning("Analysis preload failed: %s", e)
        try:
            from netwatch.forecasting.ensemble_scorer import EnsembleScorer  # noqa: F401
            from netwatch.counterfactual.simulator import CounterfactualEngine  # noqa: F401
        except Exception as e:  # noqa: BLE001
            logger.warning("Forecast/counterfactual preload failed: %s", e)

    def body() -> None:
        try:
            _build_pipeline()
            _preload_heavy_modules()
            logger.info("Background pipeline prewarm complete.")
        except Exception as e:  # noqa: BLE001
            logger.warning("Background pipeline prewarm failed: %s", e)

    threading.Thread(target=body, daemon=True, name="netwatch-prewarm").start()

ANALYSIS_STAGES = [
    ("Packet parsing", 8, "Parsing packet records."),
    ("Network State", 22, "Building temporal network states."),
    ("World Model forecast", 42, "Running LSTM world model K-step rollout."),
    ("MITRE mapping", 55, "Mapping behaviour to MITRE ATT&CK."),
    ("Explainability", 68, "Computing feature contributions."),
    ("Counterfactual simulation", 82, "Simulating defensive actions."),
    ("Ensemble analysis", 90, "Running 8 detection engines."),
    ("Analysis complete", 100, "Results ready."),
]


def _build_pipeline_unlocked(force_retrain: bool = False) -> Pipeline:
    cache_key = "default"
    if cache_key in _pipeline_cache and not force_retrain:
        return _pipeline_cache[cache_key]

    logger.info("Initializing pipeline (zero-data state; awaiting uploads)...")
    pipe = Pipeline()
    # No bundled/pre-trained dataset: results are built from uploaded traffic
    # only. `forecast_and_simulate` with no states returns a clean empty doc.
    pipe.forecast_and_simulate()
    _pipeline_cache[cache_key] = pipe
    return pipe


def _build_pipeline(force_retrain: bool = False) -> Pipeline:
    with _pipeline_lock:
        return _build_pipeline_unlocked(force_retrain)


# Pre-defined/bundled dataset artifacts are removed when the dashboard starts:
# analysis is driven purely by the uploaded capture, never by a shipped dataset.
_ARTIFACTS_CLEANED = False


def _clean_predefined_artifacts() -> None:
    global _ARTIFACTS_CLEANED
    if _ARTIFACTS_CLEANED:
        return
    _ARTIFACTS_CLEANED = True
    from netwatch.models.registry import CHECKPOINTS_DIR
    from netwatch.config import MODEL_DIR
    dirs = (MODEL_DIR, CHECKPOINTS_DIR)
    bundled_names = (
        "world_model_lstm.pt",      # shipped LSTM snapshot (now bundled no-op)
        "feature_scaler.pkl",       # shipped scaler
        "ensemble_baselines.pkl",   # shipped ensemble baselines
        "test_dummy.pkl",           # shipped pytest fixture artifact
        "registry.json",            # shipped checkpoint registry
    )
    for d in dirs:
        try:
            if d.exists():
                for f in d.iterdir():
                    if f.is_file() and f.name in bundled_names:
                        f.unlink(missing_ok=True)
        except OSError as e:  # noqa: BLE001
            logger.warning(f"Could not clean model artifacts in {d}: {e}")


def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _safe_float(v, default: float = 0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:
        return default
    return f


def _make_job(meta: dict) -> str:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "status": "queued",
        "stage": "Queued",
        "progress": 0,
        "message": "Analysis queued.",
        "created_at": datetime.now().isoformat(),
        "meta": meta,
        "result": None,
        "error": None,
    }
    with _jobs_lock:
        _jobs[job_id] = job
    return job_id


def _update_job(job_id: str, **kwargs):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job:
            job.update(kwargs)


def _get_job(job_id: str):
    with _jobs_lock:
        return _jobs.get(job_id)


# ── Canonical analysis registry helpers ───────────────────────────────────
def _get_active_analysis_id():
    with _active_analysis_lock:
        return _active_analysis_id


def _set_active_analysis(analysis_id: str):
    global _active_analysis_id
    with _active_analysis_lock:
        _active_analysis_id = analysis_id


def _register_analysis(analysis_id, doc: dict, meta: dict) -> str | None:
    """Persist a completed analysis document under one canonical id and make
    it active. Every page reads from this registry, so re-uploading the same
    capture is never required."""
    if not doc:
        return None
    try:
        doc["analysis_id"] = analysis_id
        record = {
            "analysis_id": analysis_id,
            "doc": doc,
            "created_at": (meta or {}).get("created_at") or datetime.now().isoformat(),
            "filename": doc.get("filename") or (meta or {}).get("filename"),
            "source": doc.get("source") or (meta or {}).get("source"),
        }
        with _analyses_lock:
            _analyses[analysis_id] = record
            # Keep at most a few hundred analyses in memory.
            if len(_analyses) > 300:
                for stale in list(_analyses.keys())[:50]:
                    _analyses.pop(stale, None)
        _set_active_analysis(analysis_id)
        logger.info("Registered canonical analysis %s (active) from %s",
                    analysis_id, record["filename"])
        return analysis_id
    except Exception as e:  # noqa: BLE001
        logger.exception("Could not register analysis %s: %s", analysis_id, e)
        return None


# ── Model Test Center job helpers ──────────────────────────────────────────
def _model_test_run_all_order() -> list:
    return [
        "packet_features", "flow_features", "tcp_features", "entropy",
        "temporal", "graph", "network_state", "world_model", "forecasting",
        "mitre", "explainability", "attack_graph", "counterfactual",
        "recommendation", "full_pipeline",
    ]


def _model_test_get(job_id: str):
    with _model_test_jobs_lock:
        return _model_test_jobs.get(job_id)


def _model_test_update(job_id: str, **kwargs):
    with _model_test_jobs_lock:
        job = _model_test_jobs.get(job_id)
        if job:
            job.update(kwargs)
            job["updated_at"] = datetime.now().isoformat()


def _new_model_test_job() -> str:
    """Create a backend-owned model test job and return its id."""
    from netwatch.dashboard.analysis import run_module_test
    pipe = _build_pipeline_unlocked()
    records = _get_last_records() or []

    job_id = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat()

    source = {
        "filename": _pipeline_cache.get("upload_meta", {}).get("filename") or "capture",
        "member": _pipeline_cache.get("upload_meta", {}).get("member"),
        "source": _pipeline_cache.get("upload_meta", {}).get("source"),
        "n_records": len(records),
        "n_states": len(getattr(pipe, "states", []) or []),
    }
    flow_keys = set()
    for r in records:
        flow_keys.add((getattr(r, "src_ip", ""), getattr(r, "dst_ip", ""),
                       getattr(r, "dst_port", 0), getattr(r, "protocol", "")))
    source["n_flows"] = len(flow_keys)

    module_defs = _model_test_module_defs()
    modules = [{
        "id": mid, "name": name, "description": desc,
        "status": "queued", "metrics": {}, "message": None,
    } for mid, name, desc in module_defs]

    job = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "current_module": None,
        "modules": modules,
        "source": source,
        "created_at": now,
        "started_at": None,
        "finished_at": None,
        "updated_at": now,
        "error": None,
    }
    with _model_test_jobs_lock:
        _model_test_jobs[job_id] = job
    return job_id


def _model_test_module_defs() -> list:
    defs = {
        "packet_features": ("Packet Features", "TTL, payload size and TCP window statistics."),
        "flow_features": ("Flow Features", "Flow count and flow-to-packet structure."),
        "tcp_features": ("TCP Features", "TCP handshake counts, asymmetry and RST behaviour."),
        "entropy": ("Entropy Features", "Shannon entropy of ports, hosts, sizes and flags."),
        "temporal": ("Temporal Features", "Inter-arrival time, jitter and burstiness."),
        "graph": ("Graph Features", "Topology node/edge metrics and density."),
        "network_state": ("Network State", "Windowed state construction and feature vector."),
        "world_model": ("World Model", "K-step rollout risk projection."),
        "forecasting": ("Forecasting", "Per-step risk, stage and confidence."),
        "mitre": ("MITRE Mapping", "Kill-chain stage to MITRE ATT&CK mapping."),
        "explainability": ("Explainability", "Top contributing features and temporal drivers."),
        "attack_graph": ("Attack Graph", "Predicted stage-transition graph."),
        "counterfactual": ("Counterfactual", "Defensive action risk trajectories."),
        "recommendation": ("Recommendation", "Best defensive action by predicted risk reduction."),
        "full_pipeline": ("Full Pipeline", "End-to-end ingestion -> forecast -> simulation."),
    }
    return [(mid,) + defs[mid] for mid in _model_test_run_all_order()]


def _run_single_model_test(job_id: str, module_id: str) -> dict:
    from netwatch.dashboard.analysis import run_module_test
    pipe = _build_pipeline_unlocked()
    records = _get_last_records() or []
    _model_test_update(job_id, current_module=module_id, status="running")
    result = run_module_test(module_id, pipe, records)
    with _model_test_jobs_lock:
        job = _model_test_jobs.get(job_id)
        if job and result.get("status") == "ok":
            for m in job["modules"]:
                if m["id"] == module_id:
                    m["status"] = "ok"
                    m["message"] = None
                    m["metrics"] = result.get("metrics", {})
                    m["steps"] = result.get("steps")
                    m["trajectory"] = result.get("trajectory")
                    m["graph"] = result.get("graph")
                    m["recommendation"] = result.get("recommendation")
                    m["counterfactual"] = result.get("counterfactual")
                    break
        elif job and result.get("status") == "error":
            for m in job["modules"]:
                if m["id"] == module_id:
                    m["status"] = "failed"
                    m["message"] = result.get("message", "Module failed.")
                    break
    return result


def _retry_model_test(job_id: str, module_id: str):
    """Re-run a single failed module inside an existing job."""
    try:
        _run_single_model_test(job_id, module_id)
        job = _model_test_get(job_id)
        failures = sum(1 for m in (job or {}).get("modules", []) if m.get("status") == "failed")
        _model_test_update(job_id,
                           status="completed" if not failures else "partial_failed",
                           progress=100, current_module=None,
                           finished_at=datetime.now().isoformat())
    except Exception as e:  # noqa: BLE001
        logger.exception("Retry module %s on job %s failed", module_id, job_id)
        _model_test_update(job_id, status="error", current_module=None,
                           error=str(e), finished_at=datetime.now().isoformat())


def _run_model_test_job(job_id: str):
    """Background worker: execute modules in dependency order, updating progress."""
    try:
        _model_test_update(job_id, status="running", started_at=datetime.now().isoformat(),
                           current_module="Preparing", progress=2)
        order = _model_test_run_all_order()
        total = len(order)
        for i, module_id in enumerate(order):
            _model_test_update(job_id, current_module=module_id,
                               progress=round(i / total * 100))
            _run_single_model_test(job_id, module_id)
            _model_test_update(job_id, progress=round((i + 1) / total * 100))
        job = _model_test_get(job_id)
        failures = sum(1 for m in (job or {}).get("modules", []) if m.get("status") == "failed")
        final_status = "completed" if not failures else "partial_failed"
        # REGISTER THE CANONICAL ANALYSIS. Every page reads this document, so
        # completing Run All Modules makes the analysis available everywhere
        # without the user re-uploading the capture. Must happen before the job
        # is marked terminal so the UI can adopt the analysis_id immediately.
        try:
            _publish_model_test_analysis(job_id)
        except Exception as e:  # noqa: BLE001
            logger.exception("Could not publish canonical analysis for model test job %s: %s",
                             job_id, e)
        _model_test_update(job_id, status=final_status,
                           progress=100, current_module=None,
                           finished_at=datetime.now().isoformat())
    except Exception as e:  # noqa: BLE001
        logger.exception("Model test job %s failed", job_id)
        _model_test_update(job_id, status="error", current_module=None,
                           error=str(e), finished_at=datetime.now().isoformat())


def _publish_model_test_analysis(job_id: str):
    """Build (or reuse) the canonical analysis doc for the current capture and
    store it under the model-test job id, making it the active analysis."""
    from netwatch.dashboard.analysis import build_document_from_pipeline
    pipe = _pipeline_cache.get("default")
    if pipe is None:
        return None
    records = getattr(pipe, "_last_records", None) or []
    meta = _pipeline_cache.get("upload_meta", {})
    if not records and not getattr(pipe, "states", None):
        return None
    job = _model_test_get(job_id) or {}
    source = job.get("source", {}) or {}
    filename = meta.get("filename") or source.get("filename") or "capture"
    member = meta.get("member") or source.get("member")
    source_label = meta.get("source") or source.get("source") or "User Uploaded PCAP"
    occurrence = meta.get("occurrence")
    doc = build_document_from_pipeline(
        pipe, records,
        filename=filename or "capture",
        member=member,
        source_label=source_label,
        occurrence=occurrence or (source.get("occurrence") if isinstance(source, dict) else None),
    )
    if not doc or doc.get("status") != "ok":
        return None
    _pipeline_cache["active_model_test_doc"] = doc
    _register_analysis(job_id, doc, meta={
        "filename": filename,
        "source": source_label,
        "created_at": job.get("created_at") or datetime.now().isoformat(),
    })
    _model_test_update(job_id, analysis_id=job_id)
    return job_id


def _get_last_records():
    pipe = _pipeline_cache.get("default")
    return getattr(pipe, "_last_records", None) if pipe else None


def _record_history(job_id: str, doc: dict, meta: dict):
    """Append a completed analysis summary to the in-memory history list."""
    forecast = doc.get("forecast", {}) or {}
    current = forecast.get("current", {}) or {}
    future = forecast.get("future", []) or []
    ensemble = doc.get("ensemble", {}) or {}
    consensus = ensemble.get("consensus", {}) or {}
    summary = {
        "id": job_id,
        "filename": doc.get("filename") or meta.get("filename"),
        "member": doc.get("member"),
        "source": doc.get("source") or meta.get("source", "User Uploaded PCAP"),
        "occurrence": doc.get("occurrence"),
        "created_at": meta.get("created_at", datetime.now().isoformat()),
        "n_records": doc.get("n_records", 0),
        "n_states": doc.get("n_states", 0),
        "threat_level": consensus.get("threat_level", "BENIGN"),
        "threat_status": consensus.get("threat_status", "NORMAL TRAFFIC"),
        "consensus_score": round(_safe_float(consensus.get("score")), 1),
        "current_risk": round(_safe_float(current.get("risk")), 3),
        "forecast_risk": round(_safe_float(future[-1].get("risk")), 3) if future else 0.0,
        "current_stage": current.get("stage", "Benign"),
        "predicted_stage": future[-1].get("stage", "") if future else "",
    }
    with _jobs_history_lock:
        _jobs_history.insert(0, summary)
        del _jobs_history[100:]


def _run_analysis_job(job_id: str, tmp_path, filename: str, member: str | None,
                      file_type: str, source: str, occurrence: str | None, scenario: bool):
    """Background worker: ingest the staged file and run the full pipeline."""
    _update_job(job_id, status="running", stage="Packet parsing", progress=5, message="Reading capture file.")

    def progress_fn(stage, progress, message):
        _update_job(job_id, stage=stage, progress=progress, message=message)

    tmp = Path(tmp_path) if tmp_path else None
    records = []
    extracted = None
    try:
        # ── Resolve the actual capture file ─────────────────────
        if scenario:
            from netwatch.dashboard.synthetic import generate_scenario
            records = generate_scenario(occurrence or "mixed")
            filename = f"{occurrence or 'mixed'}.sim.jsonl"
            member = None
        elif tmp and tmp.suffix.lower() == ".zip":
            _update_job(job_id, stage="Archive detected", progress=10, message="Scanning ZIP archive.")
            chosen, extracted = _extract_zip_member(tmp, member)
            if extracted is None:
                raise ValueError("No supported traffic file (.pcap, .pcapng, .csv, .jsonl) found in ZIP.")
            _update_job(job_id, stage="PCAP discovered", progress=14,
                        message=f"Analyzing {chosen}")
            records = ingest(extracted, kind=_kind_for(Path(chosen).suffix), display_name=chosen)
            member = chosen
        elif tmp:
            records = ingest(tmp, kind=file_type, display_name=filename)
        else:
            raise ValueError("No file provided.")

        if not records:
            pcap_kind = file_type in ("pcap", "pcapng") or (
                tmp and tmp.suffix.lower() in (".pcap", ".pcapng")) or (
                extracted and extracted.suffix.lower() in (".pcap", ".pcapng"))
            if pcap_kind:
                try:
                    import scapy  # noqa: F401
                except ImportError:
                    raise ValueError(
                        "PCAP parsing is disabled: the 'scapy' package is not installed "
                        "in this environment. Install it ('pip install scapy') or upload a "
                        "CSV / JSONL flow export instead.")
            raise ValueError("No valid packet or flow records found in the uploaded file.")

        # ── Run the analysis document build ─────────────────────
        from netwatch.dashboard.analysis import analyze_records

        with _pipeline_lock:
            # A fresh pipeline is trained for every analysis so results come
            # from THIS capture only — never a previous upload or bundled model.
            fresh_pipe = Pipeline()
            doc = analyze_records(records, filename=filename, member=member,
                                  source_label=source, occurrence=occurrence,
                                  progress_fn=progress_fn,
                                  pipeline_factory=lambda: fresh_pipe)
            if not doc or doc.get("status") != "ok":
                _update_job(job_id, status="error", stage="Failed",
                            message=doc.get("error", "Analysis failed.") if doc else "Analysis failed.")
                return

            fresh_pipe._last_records = records
            _pipeline_cache["default"] = fresh_pipe
            _pipeline_cache["upload_meta"] = {
                "filename": filename,
                "member": member,
                "source": source,
                "occurrence": occurrence,
                "n_records": len(records),
                "n_states": doc.get("n_states", 0),
                "uploaded_at": datetime.now().isoformat(),
            }

        _record_history(job_id, doc, meta=_get_job(job_id)["meta"])
        # Persist the analysis under the canonical job id and make it active so
        # every screen (Overview, Forecast, Graph, MITRE, ...) shares it.
        _register_analysis(job_id, doc, meta=_get_job(job_id)["meta"])
        _update_job(job_id, status="done", stage="Analysis complete", progress=100,
                    message="Results ready.", result=doc, analysis_id=job_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("Analysis job %s failed", job_id)
        _update_job(job_id, status="error", stage="Failed", message=str(e))
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink(missing_ok=True)
        if extracted is not None and Path(extracted).exists():
            try:
                Path(extracted).unlink(missing_ok=True)
            except OSError:
                pass


def _kind_for(suffix: str) -> str:
    if suffix in (".pcap", ".pcapng"):
        return "pcap"
    if suffix == ".csv":
        return "csv"
    return "jsonl"


def _extract_zip_member(zip_path: Path, member: str | None):
    """Return (chosen_member_name, extracted_tmp_path) preferring member hint."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [m for m in zf.namelist() if not m.endswith("/")]
        traffic = [m for m in members if Path(m).suffix.lower() in (".pcap", ".pcapng", ".csv", ".jsonl")]

        if member:
            chosen = next((m for m in traffic if m == member), None)
        else:
            priority = {".pcapng": 0, ".pcap": 1, ".csv": 2, ".jsonl": 3}
            chosen = min(traffic, key=lambda m: priority.get(Path(m).suffix.lower(), 99)) if traffic else None

        if chosen is None:
            return None, None

        suffix = Path(chosen).suffix.lower()
        fd, tmp_name = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        extract_path = Path(tmp_name)
        import shutil
        with zf.open(chosen) as fin, extract_path.open("wb") as fout:
            shutil.copyfileobj(fin, fout, length=1024 * 1024)
        return chosen, extract_path


def _inspect_zip(zip_path: Path, original_name: str) -> dict:
    """Return a manifest of traffic files and model artifacts inside a ZIP."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [m for m in zf.namelist() if not m.endswith("/")]
        infos = {}
        for info in zf.infolist():
            if not info.is_dir():
                infos[info.filename] = info.file_size
        traffic = []
        model_artifacts = []
        for m in sorted(members):
            suffix = Path(m).suffix.lower()
            entry = {"name": m, "size_bytes": infos.get(m, 0)}
            if suffix in (".pcap", ".pcapng", ".csv", ".jsonl"):
                entry["kind"] = _kind_for(suffix)
                traffic.append(entry)
            elif suffix in (".pt", ".pkl", ".json", ".npz"):
                model_artifacts.append(entry)
    return {
        "filename": original_name,
        "traffic_members": traffic,
        "model_artifacts": model_artifacts,
        "has_traffic": bool(traffic),
        "has_models": bool(model_artifacts),
    }


def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")

    # Remove any bundled dataset/model artifacts shipped with previous builds
    # so the dashboard only ever analyzes user-uploaded captures.
    _clean_predefined_artifacts()

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; font-src 'self' data:; "
            "img-src 'self' data:; connect-src 'self';"
        )
        return response

    @app.after_request
    def gzip_payload(response):
        # Compress text/JSON responses so the SPA boots with minimal transfer.
        if not (200 <= response.status_code < 300):
            return response
        if "gzip" not in (request.headers.get("Accept-Encoding") or ""):
            return response
        # Streaming responses (SSE live events, big file downloads) would be
        # buffered indefinitely by get_data(); never gzip them.
        if response.direct_passthrough:
            return response
        ct = (response.headers.get("Content-Type") or "").split(";")[0]
        if ct == "text/event-stream":
            return response
        if not (ct.startswith("text/") or ct in (
                "application/javascript", "application/json", "application/xml")):
            return response
        if response.headers.get("Content-Encoding"):
            return response
        data = response.get_data()
        if data is None or len(data) < 256:
            return response
        compressed = gzip.compress(data, mtime=0)
        if len(compressed) >= len(data):
            return response
        response.set_data(compressed)
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = str(len(compressed))
        response.headers["Vary"] = "Accept-Encoding"
        return response

    @app.errorhandler(413)
    def too_large(_err):
        return jsonify({"error": "Upload exceeds the 100 MB size limit."}), 413

    @app.errorhandler(404)
    def not_found(_err):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(err):
        logger.error("Unhandled server error: %s", err, exc_info=True)
        return jsonify({"error": f"Internal server error: {err}"}), 500

    # ── Health / model inspection ─────────────────────────────
    def _inspect_model_artifacts() -> dict:
        registry_models = []
        try:
            from netwatch.models.registry import ModelRegistry
            registry_models = ModelRegistry().list_models()
        except Exception as e:
            logger.warning(f"Could not read model registry: {e}")

        artifacts = []
        for d in (Path("data/data/models"),):
            if not d.exists():
                continue
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in (".pt", ".pkl", ".json", ".npz"):
                    try:
                        size_kb = f.stat().st_size / 1024.0
                    except OSError:
                        size_kb = 0.0
                    artifacts.append({
                        "name": f.name,
                        "size_kb": round(size_kb, 1),
                        "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    })
        return {"registry_models": registry_models, "artifacts": artifacts}

    # ── JSON API ──────────────────────────────────────────────
    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok", "version": __version__,
                        "models_loaded": "world_model_lstm.pt" in [a["name"] for a in _inspect_model_artifacts()["artifacts"]]})

    @app.route("/api/system")
    def api_system():
        import platform
        import sys
        from time import time
        torch_mod = sys.modules.get("torch")
        _torch = torch_mod.__version__ if torch_mod is not None else "unavailable"
        try:
            import numpy as np
            _numpy = np.__version__
        except Exception:
            _numpy = "unavailable"
        from netwatch.config import WORLD_MODEL_TYPE
        uptime = time() - getattr(api_system, "_started", time())
        api_system._started = getattr(api_system, "_started", time())
        return jsonify({
            "status": "ok",
            "app": "NetWatch Cyber World Model",
            "version": __version__,
            "started_at": datetime.fromtimestamp(getattr(api_system, "_started", time())).isoformat(),
            "uptime_seconds": round(uptime),
            "python": sys.version.split()[0],
            "torch": _torch,
            "numpy": _numpy,
            "platform": platform.platform(),
            "world_model_type": WORLD_MODEL_TYPE,
            "feature_count": 132,
        })

    @app.route("/api/ensemble")
    def api_ensemble():
        pipe = _build_pipeline()
        from netwatch.forecasting.ensemble_scorer import EnsembleScorer
        scorer = EnsembleScorer(pipeline=pipe)
        states = getattr(pipe, "states", [])
        return jsonify(scorer.evaluate_traffic(states=states, k_steps=5))

    @app.route("/api/forecast")
    def api_forecast():
        pipe = _build_pipeline()
        return jsonify(pipe.results["forecast"]["forecast"])

    @app.route("/api/graph")
    def api_graph():
        pipe = _build_pipeline()
        return jsonify(pipe.results["forecast"]["graph"])

    @app.route("/api/counterfactual")
    def api_counterfactual():
        pipe = _build_pipeline()
        return jsonify(pipe.results["forecast"]["counterfactual"])

    @app.route("/api/evaluation")
    def api_evaluation():
        pipe = _build_pipeline()
        return jsonify(pipe.results.get("evaluation", {}))

    @app.route("/api/topology")
    def api_topology():
        pipe = _build_pipeline()
        return jsonify(pipe.results["forecast"].get("network_topology", {}))

    @app.route("/api/entities")
    def api_entities():
        pipe = _build_pipeline()
        return jsonify(pipe.results["forecast"].get("entity_summary", {}))

    @app.route("/api/entities/<entity_id>")
    def api_entity_detail(entity_id):
        pipe = _build_pipeline()
        stats = pipe.network_graph.get_node_stats(entity_id)
        if stats:
            return jsonify(stats)
        return jsonify({"error": "Entity not found"}), 404

    @app.route("/api/edges/<src_id>/<dst_id>")
    def api_edge_detail(src_id, dst_id):
        pipe = _build_pipeline()
        stats = pipe.network_graph.get_edge_stats(src_id, dst_id)
        if stats:
            return jsonify(stats)
        return jsonify({"error": "Edge not found"}), 404

    @app.route("/api/mitre")
    def api_mitre():
        pipe = _build_pipeline()
        return jsonify(pipe.results["forecast"].get("mitre_trajectory", []))

    @app.route("/api/models")
    def api_models():
        pipe = _build_pipeline()
        return jsonify(pipe.model_registry.list_models())

    @app.route("/api/models/status")
    def api_models_status():
        info = _inspect_model_artifacts()
        active_meta = _pipeline_cache.get("upload_meta", {})
        return jsonify({
            "registry_models": info["registry_models"],
            "artifacts": info["artifacts"],
            "active_traffic": {
                "filename": active_meta.get("filename"),
                "member": active_meta.get("member"),
                "source": active_meta.get("source"),
                "occurrence": active_meta.get("occurrence"),
                "n_records": active_meta.get("n_records", 0),
                "n_states": active_meta.get("n_states", 0),
                "uploaded_at": active_meta.get("uploaded_at"),
            },
        })

    @app.route("/api/network-state")
    def api_network_state():
        pipe = _build_pipeline()
        from netwatch.dashboard.analysis import build_network_state_payload
        return jsonify(build_network_state_payload(getattr(pipe, "states", [])))

    # ── Async analysis workflow ──────────────────────────────
    @app.route("/api/analyze", methods=["POST"])
    def api_analyze():
        file = request.files.get("file")
        if file is None or not file.filename:
            return jsonify({"error": "No file provided"}), 400
        filename = secure_filename(file.filename)
        if not _allowed_file(filename):
            return jsonify({"error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

        member = request.form.get("member") or None
        file_type = request.form.get("file_type", "auto")

        fd, tmp_name = tempfile.mkstemp(suffix=Path(filename).suffix)
        os.close(fd)
        file.save(tmp_name)

        job_id = _make_job({
            "type": "upload",
            "filename": filename,
            "member": member,
            "source": "User Uploaded PCAP",
            "occurrence": None,
            "created_at": datetime.now().isoformat(),
        })
        t = threading.Thread(target=_run_analysis_job,
                             args=(job_id, tmp_name, filename, member, file_type, "User Uploaded PCAP", None, False),
                             daemon=True)
        t.start()
        return jsonify({"job_id": job_id})

    @app.route("/api/analyze/<job_id>")
    def api_analyze_status(job_id):
        job = _get_job(job_id)
        if not job:
            return jsonify({"error": "Analysis job not found"}), 404
        return jsonify(job)

    # ── Canonical analysis API ──────────────────────────────
    # One analysis_id per completed analysis. Every screen fetches the SAME
    # document via these endpoints, so no page requires re-uploading the capture.
    @app.route("/api/analysis/active")
    def api_analysis_active():
        aid = _get_active_analysis_id()
        with _analyses_lock:
            record = _analyses.get(aid) if aid else None
        if not record:
            return jsonify({"analysis_id": None, "doc": None})
        return jsonify({"analysis_id": aid, "doc": record["doc"]})

    @app.route("/api/analysis/<analysis_id>")
    def api_analysis_get(analysis_id):
        with _analyses_lock:
            record = _analyses.get(analysis_id)
        if not record:
            return jsonify({"error": f"Analysis `{analysis_id}` not found"}), 404
        return jsonify(record["doc"])

    @app.route("/api/zip/inspect", methods=["POST"])
    def api_zip_inspect():
        file = request.files.get("file")
        if file is None or not file.filename:
            return jsonify({"error": "No file provided"}), 400
        fd, tmp_name = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        file.save(tmp_name)
        try:
            return jsonify(_inspect_zip(Path(tmp_name), secure_filename(file.filename)))
        except zipfile.BadZipFile:
            return jsonify({"error": "The uploaded file is not a valid ZIP archive."}), 400
        finally:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass

    # ── Scenarios (clearly-labelled synthetic demos) ──────────
    @app.route("/api/scenarios")
    def api_scenarios():
        from netwatch.dashboard.synthetic import scenario_manifest
        return jsonify({"status": "ok", "source": "SYNTHETIC DATA", "scenarios": scenario_manifest()})

    @app.route("/api/scenario/run/<scenario_id>", methods=["POST"])
    def api_scenario_run(scenario_id):
        from netwatch.dashboard.synthetic import scenario_manifest
        known = {s["id"] for s in scenario_manifest()}
        if scenario_id not in known:
            return jsonify({"error": f"Unknown scenario `{scenario_id}`"}), 400

        job_id = _make_job({
            "type": "scenario",
            "filename": f"{scenario_id}.sim.jsonl",
            "member": None,
            "source": "SYNTHETIC DATA",
            "occurrence": scenario_id,
            "created_at": datetime.now().isoformat(),
        })
        t = threading.Thread(target=_run_analysis_job,
                             args=(job_id, None, f"{scenario_id}.sim.jsonl", None, "jsonl",
                                   "SYNTHETIC DATA", scenario_id, True),
                             daemon=True)
        t.start()
        return jsonify({"job_id": job_id})

    @app.route("/api/scenario", methods=["POST"])
    def api_scenario():
        data = {}
        try:
            data = request.get_json(force=True) or {}
        except Exception:
            data = {}
        try:
            k = max(1, min(10, int(data.get("k", 5))))
        except (TypeError, ValueError):
            k = 5
        actions = data.get("actions") or None
        pipe = _build_pipeline()
        if not pipe or pipe.trainer is None or not pipe.states:
            return jsonify({
                "status": "no_history",
                "results": {},
                "recommendation": {
                    "recommended_action": "no_action",
                    "recommended_label": "No Action Required (Monitor)",
                    "reason": "Upload a PCAP or run a scenario to load network data first.",
                    "risk_reduction_pct_points": 0.0,
                },
            })
        from netwatch.counterfactual.simulator import CounterfactualEngine
        history = pipe.states[-10:]
        engine = CounterfactualEngine(pipe.trainer.model,
                                      pipe.attack_forecaster,
                                      pipe.normalizer,
                                      feature_columns=pipe.feature_columns)
        sim = engine.simulate(history, actions=actions, k=k)
        rec = engine.recommend(sim)
        return jsonify({**sim, "recommendation": rec})

    # ── Legacy synchronous upload (kept for tests / compatibility) ──
    @app.route("/api/upload", methods=["POST"])
    def api_upload():
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files["file"]
        file_type = request.form.get("file_type", "auto")
        result = _process_uploaded_file(file, file_type)
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result)

    # ── Model Test Center ─────────────────────────────────────

    @app.route("/api/test-modules")
    def api_test_modules():
        pipe = _pipeline_cache.get("default")
        has_data = bool(pipe and getattr(pipe, "states", []))
        modules = [{"id": mid, "name": name, "description": desc, "has_data": has_data}
                   for mid, name, desc in _model_test_module_defs()]
        return jsonify({"modules": modules})

    @app.route("/api/test-module/<module_id>", methods=["POST"])
    def api_test_module(module_id):
        pipe = _build_pipeline()
        from netwatch.dashboard.analysis import run_module_test
        result = run_module_test(module_id, pipe, _get_last_records() or [])
        return jsonify(result)

    @app.route("/api/model-test/jobs", methods=["POST"])
    def api_model_test_create():
        pipe = _build_pipeline()
        if not getattr(pipe, "states", []) or not _get_last_records():
            return jsonify({"error": "No analysis data loaded. Upload a capture or run a scenario first."}), 409
        job_id = _new_model_test_job()
        t = threading.Thread(target=_run_model_test_job, args=(job_id,), daemon=True)
        t.start()
        return jsonify({"job_id": job_id})

    @app.route("/api/model-test/jobs")
    def api_model_test_list():
        with _model_test_jobs_lock:
            jobs = sorted(_model_test_jobs.values(),
                          key=lambda j: j.get("created_at", ""), reverse=True)
            return jsonify({"jobs": [{
                "job_id": j["job_id"], "status": j.get("status"),
                "progress": j.get("progress"), "current_module": j.get("current_module"),
                "created_at": j.get("created_at"), "finished_at": j.get("finished_at"),
                "source": j.get("source", {}),
            } for j in jobs[:50]]})

    @app.route("/api/model-test/jobs/<job_id>")
    def api_model_test_get(job_id):
        job = _model_test_get(job_id)
        if not job:
            return jsonify({"error": "Model test job not found"}), 404
        return jsonify(job)

    @app.route("/api/model-test/jobs/<job_id>/retry/<module_id>", methods=["POST"])
    def api_model_test_retry(job_id, module_id):
        job = _model_test_get(job_id)
        if not job:
            return jsonify({"error": "Model test job not found"}), 404
        if not any(m["id"] == module_id for m in job.get("modules", [])):
            return jsonify({"error": f"Unknown module: {module_id}"}), 400
        _model_test_update(job_id, status="running", current_module=module_id,
                           progress=0, error=None)
        t = threading.Thread(target=_retry_model_test, args=(job_id, module_id), daemon=True)
        t.start()
        return jsonify({"job_id": job_id, "module": module_id})

    # ── Analysis history & report ─────────────────────────────
    @app.route("/api/history")
    def api_history():
        with _jobs_history_lock:
            return jsonify({"analyses": list(_jobs_history)})

    def _current_doc():
        doc = None
        for job in list(_jobs.values()):
            if job.get("status") == "done" and job.get("result"):
                doc = job["result"]
                break
        if doc is None:
            doc = _pipeline_cache.get("last_result")
        return doc

    @app.route("/api/report")
    def api_report_current():
        from netwatch.dashboard.analysis import build_report_document
        doc = _current_doc()
        pipe = _build_pipeline()
        evaluation = pipe.results.get("evaluation", {})
        return jsonify(build_report_document(doc, evaluation, _inspect_model_artifacts()))

    @app.route("/api/report/<job_id>")
    def api_report_job(job_id):
        from netwatch.dashboard.analysis import build_report_document
        job = _get_job(job_id)
        doc = job.get("result") if job else None
        pipe = _build_pipeline()
        evaluation = pipe.results.get("evaluation", {})
        return jsonify(build_report_document(doc, evaluation, _inspect_model_artifacts()))

    @app.route("/api/retrain", methods=["POST"])
    def api_retrain():
        pipe = _build_pipeline(force_retrain=True)
        return jsonify({"status": "retrained", "n_states": len(pipe.states)})

    # ── System dependencies (Python, TShark, live capture) ────────
    @app.route("/api/system/dependencies")
    def api_system_dependencies():
        """Report Python, TShark and live capture availability."""
        import sys
        import platform
        from netwatch.live.tshark_locator import get_tshark_capabilities
        from netwatch.live.interface import discover_interfaces

        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        tshark = get_tshark_capabilities()
        interfaces = discover_interfaces()
        up_interfaces = [i for i in interfaces if str(i.get("state", "")).upper() == "UP" and not i.get("is_loopback", False)]

        return jsonify({
            "python": {
                "available": True,
                "version": python_version,
                "implementation": platform.python_implementation(),
            },
            "tshark": {
                "available": tshark.get("available", False),
                "path": tshark.get("path"),
                "version": tshark.get("version"),
                "platform": tshark.get("platform"),
                "capture_available": tshark.get("capture_available", False),
                "reason": tshark.get("reason"),
            },
            "live_capture": {
                "available": tshark.get("available", False),
                "interfaces": [i.get("name") for i in up_interfaces],
                "interface_count": len(up_interfaces),
            },
        })

    # ── Live Monitoring (TShark) API ────────────────────────────

    @app.route("/api/live/health")
    def api_live_health():
        """Check TShark availability and version."""
        from netwatch.live.health import detect_tshark
        from netwatch.live.config import TSHARK_PATH
        return jsonify(detect_tshark(TSHARK_PATH))

    @app.route("/api/live/interfaces")
    def api_live_interfaces():
        """List available network interfaces (flat shape for the SPA)."""
        from netwatch.live.interface import discover_interfaces
        raw = discover_interfaces()
        interfaces = [{
            "name": i.get("name", ""),
            "description": "",
            "addresses": [a.get("addr", "") for a in i.get("addresses", []) if a.get("addr")],
            "is_up": str(i.get("state", "")).upper() == "UP",
        } for i in raw]
        return jsonify({"interfaces": interfaces})

    @app.route("/api/live/start", methods=["POST"])
    def api_live_start():
        """Start a live TShark capture session."""
        from netwatch.live.manager import LiveManager
        from netwatch.live.config import (
            LIVE_DEFAULT_INTERFACE, LIVE_WINDOW_SIZE,
            LIVE_STEP_SIZE, LIVE_FORECAST_HORIZON,
        )
        from netwatch.live.interface import discover_interfaces
        data = {}
        try:
            data = request.get_json(force=True) or {}
        except Exception:
            data = {}
        interface = data.get("interface") or LIVE_DEFAULT_INTERFACE
        if not interface:
            available = discover_interfaces()
            return jsonify({
                "error": "Interface is required",
                "available_interfaces": [
                    {"name": i.get("name"), "description": i.get("description", "")}
                    for i in available
                ]
            }), 400
        try:
            window_size = int(data.get("window_size", LIVE_WINDOW_SIZE))
            step_size = int(data.get("step_size", LIVE_STEP_SIZE))
            forecast_horizon = int(data.get("forecast_horizon", LIVE_FORECAST_HORIZON))
        except (TypeError, ValueError) as e:
            return jsonify({"error": f"Invalid parameters: {e}"}), 400

        mgr = LiveManager()
        try:
            result = mgr.start(
                interface=interface,
                window_size=window_size,
                step_size=step_size,
                forecast_horizon=forecast_horizon,
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.exception("Live start failed")
            return jsonify({"error": f"Internal error: {e}"}), 500
        status_code = 200 if "error" not in result else 400
        return jsonify(result), status_code

    @app.route("/api/live/stop", methods=["POST"])
    def api_live_stop():
        """Stop the current live capture session."""
        from netwatch.live.manager import LiveManager
        return jsonify(LiveManager().stop())

    @app.route("/api/live/status")
    def api_live_status():
        """Return current live session status (lightweight, polled by frontend)."""
        from netwatch.live.manager import LiveManager
        mgr = LiveManager()
        if not mgr.is_active or mgr.state is None:
            return jsonify({"active": False, "status": "stopped"})
        return jsonify({"active": True, **mgr.state.to_status_dict()})

    # ── URL Monitor (destination-observed live capture) ─────────
    def _url_traffic_payload(st) -> dict:
        metrics = st.url_metrics_last or {}
        return {
            "packets": st.url_packets,
            "bytes": st.url_bytes,
            "flows": st.url_flows,
            "packets_per_second": round(metrics.get("packets_per_second", 0.0), 2),
            "bytes_per_second": round(metrics.get("bytes_per_second", 0.0), 2),
            "upload_rate": round(metrics.get("upload_rate", 0.0), 2),
            "download_rate": round(metrics.get("download_rate", 0.0), 2),
            "outbound_packets": st.url_outbound_packets,
            "outbound_bytes": st.url_outbound_bytes,
            "inbound_packets": st.url_inbound_packets,
            "inbound_bytes": st.url_inbound_bytes,
            "syn_count": st.url_syn_count,
            "rst_count": st.url_rst_count,
            "fin_count": st.url_fin_count,
            "retransmissions": st.url_retransmissions,
            "tls_connections": st.url_tls_connections,
            "resolutions": st.url_resolutions,
            "target_ip_changes": st.url_target_ip_changes,
            "active_connections": metrics.get("flows", 0),
        }

    @app.route("/api/live/url/start", methods=["POST"])
    def api_live_url_start():
        """Start a live URL-target monitoring session (DNS resolve + TShark)."""
        from netwatch.live.manager import LiveManager
        from netwatch.live.config import (
            LIVE_DEFAULT_INTERFACE, LIVE_WINDOW_SIZE,
            LIVE_STEP_SIZE, LIVE_FORECAST_HORIZON,
            LIVE_URL_ALLOW_PRIVATE_HOSTS,
        )
        data = request.get_json(force=True, silent=True) or {}
        url = data.get("url")
        if not url or not isinstance(url, str):
            return jsonify({"error": "A URL is required (e.g. https://example.com)"}), 400
        interface = data.get("interface") or LIVE_DEFAULT_INTERFACE
        if not interface:
            return jsonify({"error": "An interface is required"}), 400
        try:
            window_size = max(1, int(data.get("window_size", LIVE_WINDOW_SIZE)))
            step_size = max(1, int(data.get("step_size", LIVE_STEP_SIZE)))
            forecast_horizon = max(1, int(data.get("forecast_horizon", LIVE_FORECAST_HORIZON)))
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid window_size / step_size / forecast_horizon"}), 400

        mgr = LiveManager()
        try:
            result = mgr.start_url(
                url=url, interface=interface, window_size=window_size,
                step_size=step_size, forecast_horizon=forecast_horizon,
                allow_private_hosts=bool(LIVE_URL_ALLOW_PRIVATE_HOSTS),
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.exception("Live URL monitor start failed")
            return jsonify({"error": f"Internal error: {e}"}), 500
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result)

    @app.route("/api/live/url/status/<analysis_id>")
    def api_live_url_status(analysis_id):
        """Return the full URL monitoring status for an active session."""
        from netwatch.live.manager import LiveManager
        mgr = LiveManager()
        st = mgr.state
        if not mgr.is_active or st is None or st.mode != "live_url":
            return jsonify({"error": "No active URL monitoring session"}), 404
        if st.analysis_id != analysis_id:
            return jsonify({"error": "Analysis ID does not match active session"}), 404
        return jsonify({
            "analysis_id": st.analysis_id,
            "mode": st.mode,
            "status": st.status,
            "interface": st.interface,
            "sensor": st.sensor,
            "started_at": st.started_at,
            "source": st.source,
            "target": st.target,
            "traffic": _url_traffic_payload(st),
            "url_metrics": st.url_metrics_last,
            "timeline": list(st.timeline),
            "network_state": st.network_state,
            "risk": st.risk,
            "forecast": st.forecast,
            "stage": st.stage,
            "graph": st.graph,
            "mitre": st.mitre,
            "explainability": st.explainability,
            "counterfactual": st.counterfactual,
            "ensemble": st.ensemble,
            "world_model_status": st.world_model_status,
        })

    @app.route("/api/live/url/stop", methods=["POST"])
    def api_live_url_stop():
        """Stop a URL monitoring session cleanly (no orphan TShark processes)."""
        from netwatch.live.manager import LiveManager
        data = request.get_json(force=True, silent=True) or {}
        analysis_id = data.get("analysis_id")
        mgr = LiveManager()
        if analysis_id and mgr.state is not None and mgr.state.analysis_id != analysis_id:
            return jsonify({"error": "Analysis ID does not match active session"}), 404
        return jsonify(mgr.stop())

    @app.route("/api/live/analysis/<analysis_id>")
    def api_live_analysis_doc(analysis_id):
        """Return the full live analysis document for a given analysis_id."""
        from netwatch.live.manager import LiveManager
        mgr = LiveManager()
        if not mgr.is_active or mgr.state is None:
            return jsonify({"error": "No active live session"}), 404
        if mgr.state.analysis_id != analysis_id:
            return jsonify({"error": "Analysis ID does not match active session"}), 404
        doc = mgr.get_active_doc()
        if doc is None:
            return jsonify({"error": "Analysis document not yet available"}), 404
        return jsonify(doc)

    @app.route("/api/live/events")
    def api_live_events():
        """SSE stream of live dashboard updates (EventSource / text/event-stream)."""
        import queue
        from flask import Response, stream_with_context
        from netwatch.live.manager import LiveManager

        mgr = LiveManager()
        if not mgr.is_active:
            return jsonify({"error": "No active live session"}), 404

        q: queue.Queue = queue.Queue(maxsize=256)

        def on_event(event_type: str, data: dict):
            try:
                q.put_nowait((event_type, data))
            except queue.Full:
                pass

        mgr.subscribe(on_event)

        def generate():
            try:
                while True:
                    try:
                        event_type, data = q.get(timeout=15)
                    except queue.Empty:
                        # Keep-alive comment
                        yield ": keepalive\n\n"
                        continue
                    yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                    # If the manager stopped, send final event and close
                    if not mgr.is_active:
                        yield f"event: stopped\ndata: {json.dumps({'status': 'stopped'})}\n\n"
                        break
            finally:
                mgr.unsubscribe(on_event)

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.route("/api/live/history")
    def api_live_history():
        """Return previous live session summaries."""
        from netwatch.live.manager import LiveManager
        return jsonify({"sessions": LiveManager().get_history()})

    # ── Attack Lab API ──────────────────────────────────────────

    @app.route("/api/lab/status")
    def api_lab_status():
        """Get consolidated Attack Lab topology, target health, active attack status, and logs."""
        from netwatch.dashboard.lab_manager import LabManager
        return jsonify(LabManager().get_full_status())

    @app.route("/api/lab/target/start", methods=["POST"])
    def api_lab_target_start():
        """Start the Attack Lab target web application."""
        from netwatch.dashboard.lab_manager import LabManager
        data = request.get_json(force=True, silent=True) or {}
        port = int(data.get("port", 8080))
        host = str(data.get("host", "0.0.0.0"))
        res = LabManager().start_target_server(port=port, host=host)
        status_code = 200 if res.get("status") in ("running", "starting", "already_running") else 500
        return jsonify(res), status_code

    @app.route("/api/lab/target/stop", methods=["POST"])
    def api_lab_target_stop():
        """Stop the Attack Lab target web application."""
        from netwatch.dashboard.lab_manager import LabManager
        return jsonify(LabManager().stop_target_server())

    @app.route("/api/lab/attack/start", methods=["POST"])
    @app.route("/api/lab/attack", methods=["POST"])
    def api_lab_attack_start():
        """Launch a simulated attack against the target web application."""
        from netwatch.dashboard.lab_manager import LabManager
        data = request.get_json(force=True, silent=True) or {}
        attack_type = data.get("attack") or data.get("attack_type") or "recon"
        target_ip = data.get("target_ip")
        duration = int(data.get("duration", 15))
        intensity = str(data.get("intensity", "medium"))

        res = LabManager().start_attack(
            attack_type=attack_type,
            target_ip=target_ip,
            duration=duration,
            intensity=intensity,
        )
        status_code = 200 if res.get("status") == "started" else 400
        return jsonify(res), status_code

    @app.route("/api/lab/attack/stop", methods=["POST"])
    def api_lab_attack_stop():
        """Stop active attack simulation."""
        from netwatch.dashboard.lab_manager import LabManager
        return jsonify(LabManager().stop_attack())

    @app.route("/api/lab/events")
    def api_lab_events():
        """Return history of executed attacks."""
        from netwatch.dashboard.lab_manager import LabManager
        status = LabManager().get_full_status()
        return jsonify({
            "events": status.get("recent_events", []),
            "active_attack": status.get("active_attack"),
        })

    @app.route("/api/lab/logs")
    def api_lab_logs():
        """Return streaming logs from the Attack Lab."""
        from netwatch.dashboard.lab_manager import LabManager
        status = LabManager().get_full_status()
        return jsonify({"logs": status.get("logs", [])})

    @app.route("/api/lab/clear", methods=["POST"])
    @app.route("/api/lab/reset", methods=["POST"])
    def api_lab_clear():
        """Clear console logs and reset target stats."""
        from netwatch.dashboard.lab_manager import LabManager
        return jsonify(LabManager().clear_logs_and_stats())

    # ── Serve React frontend (SPA + real static assets) ───────
    static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    static_path = Path(static_dir)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        if path.startswith("api/"):
            return jsonify({"error": "Not found"}), 404
        candidate = static_path / path
        if path and candidate.is_file():
            resp = send_from_directory(static_dir, path)
            # Hashed, immutable assets can be cached long-term.
            if path.startswith("assets/") and "-" in path:
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
        index_file = static_path / "index.html"
        if index_file.is_file():
            resp = send_from_directory(static_dir, "index.html")
            resp.headers["Cache-Control"] = "no-cache"
            return resp
        return "<pre>Frontend build not found. Run: npm run build (or npm run dev) inside frontend/</pre>", 404

    _ensure_prewarm()

    return app


def _process_uploaded_file(file, file_type: str) -> dict:
    try:
        if not file or not file.filename:
            return {"error": "No file selected"}
        filename = secure_filename(file.filename)
        if not _allowed_file(filename):
            return {"error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}

        suffix = Path(filename).suffix.lower()

        if suffix == ".zip":
            return _process_zip_traffic(file, filename)

        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
            file.save(tmp.name)
            tmp_path = Path(tmp.name)
        try:
            records = ingest(tmp_path, kind=file_type)
            if not records:
                return {"error": "No valid packet or flow records found in uploaded file."}
            return _process_traffic_records(records, filename)
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error processing uploaded file: {e}")
        return {"error": str(e)}


def _process_zip_traffic(file, original_filename: str) -> dict:
    import tempfile as _tempfile

    with _tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        file.save(tmp.name)
        tmp_path = Path(tmp.name)
    try:
        chosen, extracted = _extract_zip_member(tmp_path, None)
        if extracted is None:
            # Maybe a model package?
            file.stream.seek(0)
            return _install_model_zip(file)
        records = ingest(extracted, kind=_kind_for(Path(chosen).suffix))
        result = _process_traffic_records(records, original_filename, member=chosen)
        if "error" not in result:
            result["source_in_zip"] = chosen
        return result
    finally:
        if extracted is not None:
            extracted.unlink(missing_ok=True)
        tmp_path.unlink(missing_ok=True)


def _process_traffic_records(records: list, filename: str, member: str | None = None) -> dict:
    """Process traffic records synchronously and cache the result."""
    if not records:
        return {"error": "No valid packet or flow records found."}

    from netwatch.dashboard.analysis import analyze_records

    with _pipeline_lock:
        pipe = _pipeline_cache.get("default")

    if pipe is None:
        pipe = _build_pipeline()

    with _pipeline_lock:
        doc = analyze_records(records, filename=filename, member=member, source_label="User Uploaded PCAP",
                              pipeline_factory=lambda: pipe)
        if not doc or doc.get("status") != "ok":
            return {"error": doc.get("error", "Analysis failed.")} if doc else {"error": "Analysis failed."}
        pipe._last_records = records
        _pipeline_cache["default"] = pipe
        _pipeline_cache["last_result"] = doc
        _pipeline_cache["upload_meta"] = {
            "filename": filename, "member": member, "source": "User Uploaded PCAP",
            "occurrence": None, "n_records": len(records),
            "n_states": doc.get("n_states", 0), "uploaded_at": datetime.now().isoformat(),
        }

    meta = {
        "filename": filename, "member": member, "source": "User Uploaded PCAP",
        "occurrence": None, "created_at": datetime.now().isoformat(),
    }
    # Persist the legacy upload as the canonical active analysis too, so every
    # screen shares the same analysis_id regardless of how the capture flowed in.
    legacy_analysis_id = uuid.uuid4().hex[:12]
    _register_analysis(legacy_analysis_id, doc, meta=meta)
    _record_history(legacy_analysis_id, doc, meta=meta)

    return {
        "status": "ok", "type": "traffic_data", "analysis_id": legacy_analysis_id,
        "n_records": len(records), "n_states": doc.get("n_states", 0),
        "forecast": doc.get("forecast", {}), "graph": doc.get("graph", {}),
        "counterfactual": doc.get("counterfactual", {}),
        "mitre_trajectory": doc.get("mitre_trajectory", []),
        "ensemble": doc.get("ensemble", {}),
    }


def _install_model_zip(zip_buffer) -> dict:
    """Extract and install a netwatch_trained_models.zip bundle, then reload the pipeline."""
    import shutil

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        zip_buffer.save(tmp.name)
        tmp_path = Path(tmp.name)

    filename = secure_filename(zip_buffer.filename or "netwatch_trained_models.zip")
    try:
        extract_temp = Path(tempfile.mkdtemp(prefix="nw_model_upload_"))
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                target = (extract_temp / member).resolve()
                if not str(target).startswith(str(extract_temp.resolve())):
                    raise ValueError("Unsafe path in archive")
            zip_ref.extractall(extract_temp)

        data_models_dir = Path("data/data/models")
        data_models_dir.mkdir(parents=True, exist_ok=True)
        checkpoints_dir = Path("models/checkpoints")
        checkpoints_dir.mkdir(parents=True, exist_ok=True)

        installed = []
        for root, _, files in os.walk(extract_temp):
            for f in files:
                if f.endswith(('.pt', '.pkl', '.json', '.npz')):
                    src_file = Path(root) / f
                    shutil.copy2(src_file, data_models_dir / f)
                    if f in ("world_model_lstm.pt", "registry.json", "feature_scaler.pkl", "ensemble_baselines.pkl"):
                        shutil.copy2(src_file, checkpoints_dir / f)
                    installed.append(f)

        shutil.rmtree(extract_temp, ignore_errors=True)

        if not installed:
            return {"error": "No valid model artifacts (.pt, .pkl, .json) found in zip file."}

        logger.info(f"Imported {len(installed)} model files from uploaded zip: {installed}")

        global _pipeline_cache
        with _pipeline_lock:
            _pipeline_cache.clear()
            try:
                pipe = Pipeline()
                pipe.load_pretrained()
                pipe.forecast_and_simulate()
                _pipeline_cache["default"] = pipe
                activated = True
            except Exception as e:  # noqa: BLE001
                logger.warning(f"New models installed but failed to reload pipeline: {e}")
                activated = False

        return {
            "status": "ok", "type": "model_package", "filename": filename,
            "n_models": len(installed), "files": installed, "activated": activated,
            "message": (
                f"Successfully imported and activated {len(installed)} model files from {filename}."
                if activated else
                f"Imported {len(installed)} model files, but in-memory reload failed."
            ),
        }
    finally:
        tmp_path.unlink(missing_ok=True)


app = create_app()

if __name__ == "__main__":
    debug_mode = DASHBOARD_DEBUG and os.environ.get("FLASK_ENV") != "production"
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=debug_mode, threaded=True)