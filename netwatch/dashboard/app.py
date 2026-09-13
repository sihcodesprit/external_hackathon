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

_pipeline_cache = {}
_pipeline_lock = threading.Lock()

ALLOWED_EXTENSIONS = {".pcap", ".pcapng", ".csv", ".jsonl", ".zip"}
MAX_FILE_SIZE = 100 * 1024 * 1024

# ── Async analysis job manager ────────────────────────────────────────────
_jobs = {}
_jobs_lock = threading.Lock()
_jobs_history = []          # summary entries for the Analysis History screen
_jobs_history_lock = threading.Lock()

# Lazy background prewarm so the first page request never blocks
# behind the (heavy) pipeline load: assets and health answer instantly.
_PREWARM_STARTED = False
_SYSTEM_TORCH = "unavailable"   # filled by the background prewarm thread


def _ensure_prewarm() -> None:
    global _PREWARM_STARTED
    if _PREWARM_STARTED:
        return
    if os.environ.get("NETWATCH_SKIP_PREWARM") == "1":
        return
    _PREWARM_STARTED = True

    def body() -> None:
        global _SYSTEM_TORCH
        try:
            _build_pipeline()
            logger.info("Background pipeline prewarm complete.")
        except Exception as e:  # noqa: BLE001
            logger.warning("Background pipeline prewarm failed: %s", e)
        try:
            import torch  # warm lazily so /api/system never blocks a request
            _SYSTEM_TORCH = torch.__version__
        except Exception:  # noqa: BLE001
            pass

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

    logger.info("Initializing pipeline (loading pre-trained models)...")
    pipe = Pipeline()
    pipe.load_pretrained()
    pipe.forecast_and_simulate()
    logger.info("Pipeline ready (zero-data state; awaiting user capture uploads).")
    _pipeline_cache[cache_key] = pipe
    return pipe


def _build_pipeline(force_retrain: bool = False) -> Pipeline:
    with _pipeline_lock:
        return _build_pipeline_unlocked(force_retrain)


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
            records = ingest(extracted, kind=_kind_for(Path(chosen).suffix))
            member = chosen
        elif tmp:
            records = ingest(tmp, kind=file_type)
        else:
            raise ValueError("No file provided.")

        if not records:
            raise ValueError("No valid packet or flow records found in the uploaded file.")

        # ── Run the analysis document build ─────────────────────
        from netwatch.dashboard.analysis import analyze_records

        with _pipeline_lock:
            pipe = _pipeline_cache.get("default")

        if pipe is None:
            pipe = _build_pipeline()

        with _pipeline_lock:
            doc = analyze_records(records, filename=filename, member=member,
                                  source_label=source, occurrence=occurrence,
                                  progress_fn=progress_fn,
                                  pipeline_factory=lambda: pipe)
            if not doc or doc.get("status") != "ok":
                _update_job(job_id, status="error", stage="Failed",
                            message=doc.get("error", "Analysis failed.") if doc else "Analysis failed.")
                return

            pipe._last_records = records
            _pipeline_cache["default"] = pipe
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
        _update_job(job_id, status="done", stage="Analysis complete", progress=100,
                    message="Results ready.", result=doc)
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
        with extract_path.open("wb") as fout:
            with zf.open(chosen) as fin:
                fout.write(fin.read())
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
        ct = (response.headers.get("Content-Type") or "").split(";")[0]
        if not (ct.startswith("text/") or ct in (
                "application/javascript", "application/json", "application/xml")):
            return response
        if response.headers.get("Content-Encoding"):
            return response
        if response.direct_passthrough:
            response.direct_passthrough = False
            response.get_data(as_text=False)  # buffer the streamed file
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
    def internal_error(_err):
        return jsonify({"error": "Internal server error"}), 500

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
        _torch = _SYSTEM_TORCH
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
    MODULE_TEST_DEFS = [
        ("packet_features", "Packet Features", "TTL, payload size and TCP window statistics."),
        ("flow_features", "Flow Features", "Flow count and flow-to-packet structure."),
        ("tcp_features", "TCP Features", "TCP handshake counts, asymmetry and RST behaviour."),
        ("entropy", "Entropy Features", "Shannon entropy of ports, hosts, sizes and flags."),
        ("temporal", "Temporal Features", "Inter-arrival time, jitter and burstiness."),
        ("graph", "Graph Features", "Topology node/edge metrics and density."),
        ("network_state", "Network State", "Windowed state construction and feature vector."),
        ("world_model", "World Model", "LSTM K-step rollout risk projection."),
        ("forecasting", "Forecasting", "Per-step risk, stage and confidence."),
        ("mitre", "MITRE Mapping", "Kill-chain stage to MITRE ATT&CK mapping."),
        ("explainability", "Explainability", "Top contributing features and temporal drivers."),
        ("attack_graph", "Attack Graph", "Predicted stage-transition graph."),
        ("counterfactual", "Counterfactual", "Defensive action risk trajectories."),
        ("recommendation", "Recommendation", "Best defensive action by predicted risk reduction."),
        ("full_pipeline", "Full Pipeline", "End-to-end ingestion → forecast → simulation."),
    ]

    @app.route("/api/test-modules")
    def api_test_modules():
        pipe = _pipeline_cache.get("default")
        has_data = bool(pipe and getattr(pipe, "states", []))
        modules = [{"id": mid, "name": name, "description": desc, "has_data": has_data}
                   for mid, name, desc in MODULE_TEST_DEFS]
        return jsonify({"modules": modules})

    @app.route("/api/test-module/<module_id>", methods=["POST"])
    def api_test_module(module_id):
        pipe = _build_pipeline()
        from netwatch.dashboard.analysis import run_module_test
        result = run_module_test(module_id, pipe, _get_last_records() or [])
        return jsonify(result)

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
        result = _process_traffic_records(records, original_filename)
        if "error" not in result:
            result["source_in_zip"] = chosen
        return result
    finally:
        if extracted is not None:
            extracted.unlink(missing_ok=True)
        tmp_path.unlink(missing_ok=True)


def _process_traffic_records(records: list, filename: str) -> dict:
    """Process traffic records synchronously and cache the result."""
    if not records:
        return {"error": "No valid packet or flow records found."}

    from netwatch.dashboard.analysis import analyze_records

    with _pipeline_lock:
        pipe = _pipeline_cache.get("default")

    if pipe is None:
        pipe = _build_pipeline()

    with _pipeline_lock:
        doc = analyze_records(records, filename=filename, source_label="User Uploaded PCAP",
                              pipeline_factory=lambda: pipe)
        if not doc or doc.get("status") != "ok":
            return {"error": doc.get("error", "Analysis failed.")} if doc else {"error": "Analysis failed."}
        pipe._last_records = records
        _pipeline_cache["default"] = pipe
        _pipeline_cache["last_result"] = doc
        _pipeline_cache["upload_meta"] = {
            "filename": filename, "member": None, "source": "User Uploaded PCAP",
            "occurrence": None, "n_records": len(records),
            "n_states": doc.get("n_states", 0), "uploaded_at": datetime.now().isoformat(),
        }

    _record_history(uuid.uuid4().hex[:12], doc, meta={
        "filename": filename, "source": "User Uploaded PCAP", "occurrence": None,
        "created_at": datetime.now().isoformat()})

    return {
        "status": "ok", "type": "traffic_data",
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