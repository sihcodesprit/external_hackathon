"""
Flask dashboard for the Counterfactual Cyber World Model.

Serves 8 pages:
  1. Dashboard (live risk + latest forecast summary)
  2. 10-Min Prediction Radar
  3. Predicted Attack Graph
  4. Counterfactual Simulation
  5. Attack Stage Timeline
  6. Risk & Explainability (SHAP)
  7. Model Evaluation
  8. Scenario / Data Explorer
  9. Upload / Demo (NEW: PCAP/CSV upload, demo mode)

The dashboard lazily instantiates the Pipeline on first request (trains the
World Model on synthetic data) and caches the results.
"""

import functools
import logging
import os
import tempfile
import threading
from pathlib import Path
from werkzeug.utils import secure_filename

from flask import Flask, jsonify, render_template, request, flash, redirect, url_for

from netwatch import __version__
from netwatch.config import DASHBOARD_DEBUG, DASHBOARD_PORT, DASHBOARD_HOST
from netwatch.ingestion.parser import ingest
from netwatch.pipeline import Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global pipeline cache
_pipeline_cache = {}
_pipeline_lock = threading.Lock()

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {".pcap", ".pcapng", ".csv", ".jsonl"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def _build_pipeline(force_retrain: bool = False) -> Pipeline:
    """Train the world model once and cache it for the process lifetime."""
    global _pipeline_cache
    
    with _pipeline_lock:
        cache_key = "default"
        if cache_key in _pipeline_cache and not force_retrain:
            return _pipeline_cache[cache_key]
        
        logger.info("Initializing pipeline (world model training)...")
        pipe = Pipeline()
        data_info = pipe.load_data(n_traces=4, seed=42)
        train_info = pipe.train()
        eval_info = pipe.evaluate()
        forecast_info = pipe.forecast_and_simulate()
        logger.info("Pipeline ready.")
        
        _pipeline_cache[cache_key] = pipe
        return pipe


def _allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _process_uploaded_file(file, file_type: str) -> dict:
    """Process an uploaded PCAP or CSV file and run forecasting."""
    try:
        # Validate filename
        if not file or not file.filename:
            return {"error": "No file selected"}
        
        # Secure the filename
        filename = secure_filename(file.filename)
        if not _allowed_file(filename):
            return {"error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}
        
        # Save to temp file with secure name
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
            file.save(tmp.name)
            tmp_path = Path(tmp.name)
        
        try:
            # Ingest the file
            records = ingest(tmp_path, kind=file_type)
            
            if not records:
                return {"error": "No valid records found in file"}
            
            # Build states
            from netwatch.features.network_state import StateBuilder
            builder = StateBuilder(group_by_pair=False)
            states = builder.build_states(records)
            
            if not states:
                return {"error": "No valid network states could be generated"}
            
            # Get or create pipeline
            pipe = _build_pipeline()
            
            # Use the trained model to forecast on new data
            # Normalize states with existing normalizer
            norm_states = [pipe.normalizer.transform(s) for s in states]
            
            # Take last sequence_length states for forecasting
            seq_len = pipe.trainer.model.sequence_length or 10
            if len(norm_states) < seq_len:
                return {"error": f"Need at least {seq_len} windows, got {len(norm_states)}"}
            
            history = norm_states[-seq_len:]
            
            # Run forecast
            forecast = pipe.attack_forecaster.forecast(states[-seq_len:], k=5)
            
            # Build graph
            from netwatch.graph.predictive_attack_graph import build_predictive_graph
            graph = build_predictive_graph(forecast)
            
            # Counterfactual simulation
            from netwatch.counterfactual.simulator import CounterfactualEngine
            from netwatch.config import DEFAULT_ACTIONS
            engine = CounterfactualEngine(
                pipe.trainer.model, pipe.attack_forecaster, pipe.normalizer
            )
            sim = engine.simulate(states[-seq_len:], actions=DEFAULT_ACTIONS, k=5)
            rec = engine.recommend(sim)
            
            # MITRE mapping
            stages = [forecast["current"]["stage"]] + [st["stage"] for st in forecast["future"]]
            mitre = pipe.attack_mapper.map_trajectory(stages)
            
            # Explanations
            for step in forecast["future"]:
                step["explanation"] = pipe.explainer.explain(step["state_vec"], step["features"])
            forecast["current"]["explanation"] = pipe.explainer.explain(
                forecast["current"]["state_vec"], forecast["current"]["features"])
            
            return {
                "status": "ok",
                "n_records": len(records),
                "n_states": len(states),
                "forecast": forecast,
                "graph": graph,
                "counterfactual": {**sim, "recommendation": rec},
                "mitre_trajectory": mitre,
            }
            
        finally:
            # Clean up temp file
            tmp_path.unlink(missing_ok=True)
            
    except Exception as e:
        logger.error(f"Error processing uploaded file: {e}")
        return {"error": str(e)}


def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE
    app.jinja_env.globals["zip"] = zip
    # Use environment variable for secret key in production
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-production")
    
    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:;"
        return response

    @app.route("/")
    def index():
        return dashboard()

    @app.route("/dashboard")
    def dashboard():
        pipe = _build_pipeline()
        forecast = pipe.results["forecast"]
        current = forecast["forecast"]["current"]
        rec = forecast["counterfactual"]["recommendation"]
        return render_template("dashboard.html", version=__version__,
                               current=current, recommendation=rec)

    @app.route("/radar")
    def radar():
        pipe = _build_pipeline()
        forecast = pipe.results["forecast"]["forecast"]
        return render_template("radar.html", version=__version__,
                               forecast=forecast)

    @app.route("/graph")
    def attack_graph():
        pipe = _build_pipeline()
        graph = pipe.results["forecast"]["graph"]
        return render_template("graph.html", version=__version__,
                               graph_json=graph)

    @app.route("/counterfactual")
    def counterfactual():
        pipe = _build_pipeline()
        sim = pipe.results["forecast"]["counterfactual"]
        return render_template("counterfactual.html", version=__version__,
                               simulation=sim)

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
        return render_template("explainability.html", version=__version__,
                               forecast=forecast)

    @app.route("/evaluation")
    def evaluation():
        pipe = _build_pipeline()
        evals = pipe.results.get("evaluation", {})
        return render_template("evaluation.html", version=__version__,
                               evals=evals)

    @app.route("/scenarios")
    def scenarios():
        pipe = _build_pipeline()
        return render_template("scenarios.html", version=__version__)

    # NEW: Upload/Demo page
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
                else:
                    file_type = "jsonl"
            
            result = _process_uploaded_file(file, file_type)
            
            if "error" in result:
                flash(f"Error: {result['error']}")
                return redirect(request.url)
            
            return render_template("upload_result.html", version=__version__,
                                   result=result, filename=file.filename)
        
        return render_template("upload.html", version=__version__)

    # NEW: Demo mode page
    @app.route("/demo")
    def demo():
        """Demo mode with pre-configured attack scenarios."""
        pipe = _build_pipeline()
        forecast = pipe.results["forecast"]["forecast"]
        sim = pipe.results["forecast"]["counterfactual"]
        return render_template("demo.html", version=__version__,
                               forecast=forecast, simulation=sim)

    # ── JSON API endpoints ─────────────────────────────────
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

    @app.route("/api/scenario", methods=["POST"])
    def api_scenario():
        """Run an ad-hoc scenario: re-simulate with chosen params."""
        data = request.get_json(force=True) or {}
        k = int(data.get("k", 5))
        actions = data.get("actions") or None
        n_traces = int(data.get("n_traces", 10))
        pipe = _build_pipeline()
        from netwatch.counterfactual.simulator import CounterfactualEngine
        history = pipe.states[-10:]
        engine = CounterfactualEngine(pipe.trainer.model,
                                      pipe.attack_forecaster,
                                      pipe.normalizer)
        sim = engine.simulate(history, actions=actions, k=k)
        rec = engine.recommend(sim)
        return jsonify({**sim, "recommendation": rec})

    @app.route("/api/upload", methods=["POST"])
    def api_upload():
        """API endpoint for file upload."""
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
        """Force retrain the pipeline."""
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
    # Disable debug mode in production
    debug_mode = DASHBOARD_DEBUG and os.environ.get("FLASK_ENV") != "production"
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=debug_mode)