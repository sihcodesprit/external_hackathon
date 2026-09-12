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

    # ── Serve React frontend ──────────────────────────────────
    from flask import send_from_directory, jsonify, abort

    static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        if path.startswith("api/"):
            return jsonify({"error": "Not found"}), 404
        try:
            return send_from_directory(static_dir, "index.html")
        except Exception:
            abort(404)

    return app


app = create_app()

if __name__ == "__main__":
    debug_mode = DASHBOARD_DEBUG and os.environ.get("FLASK_ENV") != "production"
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=debug_mode)
