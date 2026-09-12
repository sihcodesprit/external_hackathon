"""
Flask dashboard — SOC-style interface for the Counterfactual Cyber World Model.

Serves pages:
  1. SOC Dashboard (risk overview + network topology)
  2. Network Topology (interactive graph view)
  3. Forecast View (K-step risk timeline)
  4. Attack Graph (predicted stage transitions)
  5. Counterfactual Simulation
  6. Explainability (SHAP + temporal)
  7. Evaluation
  8. Model Test Center (test each component separately)
  9. Upload / Demo
"""

import functools
import json
import logging
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename

from flask import Flask, jsonify, render_template, request, flash, redirect, url_for

from netwatch import __version__
from netwatch.config import DASHBOARD_DEBUG, DASHBOARD_PORT, DASHBOARD_HOST
from netwatch.features.network_state import StateBuilder
from netwatch.forecasting.ensemble_scorer import EnsembleScorer
from netwatch.ingestion.parser import ingest
from netwatch.pipeline import Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_pipeline_cache = {}
_pipeline_lock = threading.Lock()

ALLOWED_EXTENSIONS = {".pcap", ".pcapng", ".csv", ".jsonl", ".zip"}
MAX_FILE_SIZE = 100 * 1024 * 1024


def _build_pipeline(force_retrain: bool = False) -> Pipeline:
    global _pipeline_cache
    with _pipeline_lock:
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


def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _install_model_zip(zip_buffer) -> dict:
    """Extract and install a netwatch_trained_models.zip bundle, then reload the pipeline."""
    import zipfile
    import shutil

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        zip_buffer.save(tmp.name)
        tmp_path = Path(tmp.name)

    filename = secure_filename(zip_buffer.filename or "netwatch_trained_models.zip")
    try:
        extract_temp = Path(tempfile.mkdtemp(prefix="nw_model_upload_"))
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
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

        # Reload the in-memory pipeline so the new weights activate immediately
        global _pipeline_cache
        with _pipeline_lock:
            _pipeline_cache.clear()
            try:
                pipe = Pipeline()
                pipe.load_pretrained()
                pipe.forecast_and_simulate()
                _pipeline_cache["default"] = pipe
                activated = True
            except Exception as e:
                logger.warning(f"New models installed but failed to reload pipeline: {e}")
                activated = False

        return {
            "status": "ok",
            "type": "model_package",
            "filename": filename,
            "n_models": len(installed),
            "files": installed,
            "activated": activated,
            "message": (
                f"Successfully imported and activated {len(installed)} model files from {filename}."
                if activated else
                f"Imported {len(installed)} model files, but in-memory reload failed."
            ),
        }
    finally:
        tmp_path.unlink(missing_ok=True)


def _inspect_model_artifacts() -> dict:
    """Return metadata about the installed model artifacts for the Models page."""
    registry_models = []
    try:
        registry_models = _build_pipeline().model_registry.list_models()
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
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                        if f.stat().st_mtime else "",
                })

    return {
        "registry_models": registry_models,
        "artifacts": artifacts,
        "active_meta": _pipeline_cache.get("upload_meta", {}),
    }


def _process_traffic_records(records: list, filename: str) -> dict:
    """Process traffic records through the pipeline and return result dict."""
    if not records:
        return {"error": "No valid packet or flow records found."}
    
    pipe = _build_pipeline()
    data_info = pipe.load_data(records=records)
    states = pipe.states
    if not states:
        return {"error": "Traffic was parsed, but not enough temporal windows could be formed to build network states."}

    sim_out = pipe.forecast_and_simulate(k=5)
    forecast = sim_out["forecast"]
    graph = sim_out["graph"]
    counterfactual = sim_out["counterfactual"]
    mitre = sim_out.get("mitre_trajectory", [])

    scorer = EnsembleScorer(pipeline=pipe)
    ensemble_res = scorer.evaluate_traffic(records=records, states=states, k_steps=5)

    global _pipeline_cache
    with _pipeline_lock:
        _pipeline_cache["default"] = pipe
        _pipeline_cache["upload_meta"] = {
            "filename": filename,
            "n_records": len(records),
            "n_states": len(states),
            "uploaded_at": datetime.now().isoformat(),
        }

    return {
        "status": "ok",
        "type": "traffic_data",
        "n_records": len(records),
        "n_states": len(states),
        "forecast": forecast,
        "graph": graph,
        "counterfactual": counterfactual,
        "mitre_trajectory": mitre,
        "ensemble": ensemble_res,
    }


def _process_zip_traffic(file, original_filename: str) -> dict:
    """Extract traffic file (.pcap/.pcapng/.csv/.jsonl) from a ZIP archive and process it.
    
    If the ZIP contains model artifacts instead, falls back to _install_model_zip.
    """
    import zipfile
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        file.save(tmp.name)
        tmp_path = Path(tmp.name)
    
    try:
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
            # List all members
            members = zip_ref.namelist()
            if not members:
                return {"error": "ZIP file is empty."}
            
            # Find traffic files (prefer pcap > csv > jsonl)
            traffic_members = []
            model_artifacts = []
            
            for member in members:
                if member.endswith('/'):
                    continue
                suffix = Path(member).suffix.lower()
                if suffix in {".pcap", ".pcapng", ".csv", ".jsonl"}:
                    traffic_members.append((member, suffix))
                elif suffix in {".pt", ".pkl", ".json", ".npz"}:
                    model_artifacts.append(member)
            
            # If traffic files found, extract the best one
            if traffic_members:
                # Priority: .pcapng > .pcap > .csv > .jsonl
                priority = {".pcapng": 0, ".pcap": 1, ".csv": 2, ".jsonl": 3}
                traffic_members.sort(key=lambda x: priority.get(x[1], 99))
                member_name, member_suffix = traffic_members[0]
                
                # Extract to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=member_suffix) as extract_tmp:
                    extract_tmp_path = Path(extract_tmp.name)
                try:
                    with zipfile.ZipFile(tmp_path, 'r') as zf:
                        zf.extract(member_name, path=extract_tmp_path.parent)
                    extracted = extract_tmp_path.parent / member_name
                    
                    # Determine kind from suffix
                    if member_suffix in {".pcap", ".pcapng"}:
                        kind = "pcap"
                    elif member_suffix == ".csv":
                        kind = "csv"
                    else:
                        kind = "jsonl"
                    
                    records = ingest(extracted, kind=kind)
                    result = _process_traffic_records(records, original_filename)
                    if "error" not in result:
                        result["source_in_zip"] = member_name
                    return result
                finally:
                    if extracted.exists():
                        extracted.unlink(missing_ok=True)
                    if extract_tmp_path.exists():
                        extract_tmp_path.unlink(missing_ok=True)
            
            # If model artifacts found, delegate to model installer
            if model_artifacts:
                # Reset file pointer for _install_model_zip
                file.stream.seek(0)
                return _install_model_zip(file)
            
            return {"error": "No traffic files (.pcap, .pcapng, .csv, .jsonl) or model artifacts found in ZIP."}
    finally:
        tmp_path.unlink(missing_ok=True)


def _process_uploaded_file(file, file_type: str) -> dict:
    try:
        if not file or not file.filename:
            return {"error": "No file selected"}
        filename = secure_filename(file.filename)
        if not _allowed_file(filename):
            return {"error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}

        suffix = Path(filename).suffix.lower()

        # ── Handle .zip: auto-detect traffic vs model bundle ────────
        if suffix == ".zip":
            return _process_zip_traffic(file, filename)

        # ── Handle Network Traffic Ingestion (PCAP / CSV / JSONL) ──
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
    except Exception as e:
        logger.error(f"Error processing uploaded file: {e}")
        return {"error": str(e)}


def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE
    app.jinja_env.globals["zip"] = zip
    app.jinja_env.globals["enumerate"] = enumerate
    
    def get_stage_badge_class(stage):
        s = (stage or "").lower()
        if "recon" in s or "discovery" in s:
            return "badge-info"
        if "initial" in s or "execution" in s or "privilege" in s or "defense" in s or "credential" in s:
            return "badge-warning"
        if "lateral" in s or "collection" in s or "exfil" in s or "command" in s or "impact" in s:
            return "badge-danger"
        return "badge-neutral"
    
    app.jinja_env.globals["getStageBadgeClass"] = get_stage_badge_class
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:;")
        return response

    @app.route("/")
    def index():
        return dashboard()

    @app.route("/dashboard")
    def dashboard():
        pipe = _build_pipeline()
        forecast_data = pipe.results.get("forecast", {})
        fc = forecast_data.get("forecast", {})
        current = fc.get("current", {"risk": 0.0, "stage": "Benign", "confidence": 0.0})
        rec = forecast_data.get("counterfactual", {}).get("recommendation", {
            "recommended_label": "No Action", "reason": "System operating normally", "risk_reduction_pct_points": 0.0
        })
        topology = forecast_data.get("network_topology", {})
        entities = forecast_data.get("entity_summary", {})
        forecast_steps = fc.get("future", [])
        return render_template("dashboard.html", version=__version__,
                               current=current, recommendation=rec,
                               topology=topology, entities=entities,
                               forecast_steps=forecast_steps)

    @app.route("/topology")
    def topology():
        pipe = _build_pipeline()
        topo = pipe.results["forecast"].get("network_topology", {})
        return render_template("topology.html", version=__version__, topology=topo)

    @app.route("/radar")
    def radar():
        pipe = _build_pipeline()
        forecast = pipe.results["forecast"]["forecast"]
        return render_template("radar.html", version=__version__, forecast=forecast)

    @app.route("/graph")
    def attack_graph():
        pipe = _build_pipeline()
        graph = pipe.results["forecast"]["graph"]
        return render_template("graph.html", version=__version__, graph_json=graph)

    @app.route("/counterfactual")
    def counterfactual():
        pipe = _build_pipeline()
        sim = pipe.results["forecast"]["counterfactual"]
        return render_template("counterfactual.html", version=__version__, simulation=sim)

    @app.route("/stages")
    def stages():
        pipe = _build_pipeline()
        forecast = pipe.results["forecast"]["forecast"]
        mitre = pipe.results["forecast"]["mitre_trajectory"]
        return render_template("stages.html", version=__version__,
                               forecast=forecast, mitre=mitre)

    @app.route("/explainability")
    def explainability():
        pipe = _build_pipeline()
        forecast = pipe.results["forecast"]["forecast"]
        return render_template("explainability.html", version=__version__, forecast=forecast)

    @app.route("/evaluation")
    def evaluation():
        pipe = _build_pipeline()
        evals = pipe.results.get("evaluation", {})
        return render_template("evaluation.html", version=__version__, evals=evals)

    @app.route("/test-center")
    def test_center():
        pipe = _build_pipeline()
        return render_template("test_center.html", version=__version__)

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        if request.method == "POST":
            if "file" not in request.files:
                flash("No file selected")
                return redirect(request.url)
            file = request.files["file"]
            if file.filename == "":
                flash("No file selected")
                return redirect(request.url)
            file_type = request.form.get("file_type", "auto")
            if file_type == "auto":
                if file.filename.lower().endswith((".pcap", ".pcapng")):
                    file_type = "pcap"
                elif file.filename.lower().endswith(".csv"):
                    file_type = "csv"
                elif file.filename.lower().endswith(".zip"):
                    file_type = "zip"
                else:
                    file_type = "jsonl"
            result = _process_uploaded_file(file, file_type)
            if "error" in result:
                flash(f"Error: {result['error']}")
                return redirect(request.url)
            return render_template("upload_result.html", version=__version__, result=result, filename=file.filename)
        return render_template("upload.html", version=__version__)

    @app.route("/models", methods=["GET", "POST"])
    def models():
        """Dedicated Model Management page — upload .zip bundles, view active weights, reload."""
        if request.method == "POST":
            if "model_zip" not in request.files or request.files["model_zip"].filename == "":
                flash("No model zip file selected")
                return redirect("/models")
            file = request.files["model_zip"]
            if not file.filename.lower().endswith(".zip"):
                flash("Model upload must be a .zip file (e.g. netwatch_trained_models.zip)")
                return redirect("/models")
            result = _install_model_zip(file)
            if "error" in result:
                flash(f"Error: {result['error']}")
            else:
                flash(f"✓ {result['message']}")
            return redirect("/models")

        info = _inspect_model_artifacts()
        return render_template("models.html", version=__version__,
                               models=info["registry_models"],
                               artifacts=info["artifacts"],
                               active_meta=info["active_meta"])

    @app.route("/models/reload", methods=["POST"])
    def models_reload():
        """Reload pre-trained weights from disk into the active pipeline,
        preserving any currently-uploaded traffic session."""
        global _pipeline_cache
        with _pipeline_lock:
            prev = _pipeline_cache.get("default")
            prev_states = list(prev.states) if prev is not None else []
            prev_meta = _pipeline_cache.get("upload_meta", {})
            _pipeline_cache.clear()
            try:
                pipe = Pipeline()
                ok = pipe.load_pretrained()
                if prev_states:
                    pipe.states = prev_states
                    pipe.forecast_and_simulate()
                _pipeline_cache["default"] = pipe
                if prev_meta:
                    _pipeline_cache["upload_meta"] = prev_meta
                reloaded = True
                message = ("Pre-trained weights reloaded and active." if ok
                           else "Models reloaded, but no pre-trained weights found on disk.")
            except Exception as e:
                logger.error(f"Failed to reload models: {e}")
                _pipeline_cache.pop("default", None)
                return jsonify({"status": "error", "message": str(e)}), 500
        n_models = len(_inspect_model_artifacts()["artifacts"])
        return jsonify({
            "status": "ok" if reloaded else "degraded",
            "message": message,
            "n_models": n_models,
            "preserved_states": len(prev_states),
        })

    @app.route("/ensemble", methods=["GET", "POST"])
    def ensemble():
        pipe = _build_pipeline()
        scorer = EnsembleScorer(pipeline=pipe)
        
        if request.method == "POST":
            if "file" not in request.files or request.files["file"].filename == "":
                flash("No file selected")
                return redirect(request.url)
            file = request.files["file"]
            file_type = request.form.get("file_type", "auto")
            if file_type == "auto":
                if file.filename.lower().endswith((".pcap", ".pcapng")):
                    file_type = "pcap"
                elif file.filename.lower().endswith(".csv"):
                    file_type = "csv"
                elif file.filename.lower().endswith(".zip"):
                    file_type = "zip"
                else:
                    file_type = "jsonl"
            result = _process_uploaded_file(file, file_type)
            if "error" in result:
                flash(f"Error: {result['error']}")
                return redirect(request.url)
            return render_template("ensemble.html", version=__version__,
                                   ensemble=result.get("ensemble"), filename=file.filename,
                                   is_uploaded=True)
        
        # Default: evaluate active pipeline traffic states
        states = getattr(pipe, "states", [])
        ensemble_results = scorer.evaluate_traffic(states=states, k_steps=5)
        return render_template("ensemble.html", version=__version__,
                               ensemble=ensemble_results, filename="Active Pipeline Replay Data",
                               is_uploaded=False)

    @app.route("/demo")
    def demo():
        return redirect(url_for("dashboard"))

    @app.route("/scenarios")
    def scenarios():
        pipe = _build_pipeline()
        return render_template("scenarios.html", version=__version__)

    # ── JSON API ────────────────────────────────────────────
    @app.route("/api/ensemble")
    def api_ensemble():
        pipe = _build_pipeline()
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
                "n_records": active_meta.get("n_records", 0),
                "n_states": active_meta.get("n_states", 0),
                "uploaded_at": active_meta.get("uploaded_at"),
            },
        })

    @app.route("/api/scenario", methods=["POST"])
    def api_scenario():
        data = request.get_json(force=True) or {}
        k = int(data.get("k", 5))
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

    @app.route("/api/retrain", methods=["POST"])
    def api_retrain():
        pipe = _build_pipeline(force_retrain=True)
        return jsonify({"status": "retrained", "n_states": len(pipe.states)})

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(413)
    def too_large(_):
        return jsonify({"error": "File too large (max 100MB)"}), 413

    return app


app = create_app()

if __name__ == "__main__":
    debug_mode = DASHBOARD_DEBUG and os.environ.get("FLASK_ENV") != "production"
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=debug_mode)
