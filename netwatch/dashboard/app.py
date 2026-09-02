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

The dashboard lazily instantiates the Pipeline on first request (trains the
World Model on synthetic data) and caches the results.
"""

import functools
import logging

from flask import Flask, jsonify, render_template, request

from netwatch import __version__
from netwatch.pipeline import Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def _build_pipeline() -> Pipeline:
    """Train the world model once and cache it for the process lifetime."""
    logger.info("Initializing pipeline (world model training)...")
    pipe = Pipeline()
    data_info = pipe.load_data(n_traces=4, seed=42)
    train_info = pipe.train()
    eval_info = pipe.evaluate()
    forecast_info = pipe.forecast_and_simulate()
    logger.info("Pipeline ready.")
    return pipe


def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.jinja_env.globals["zip"] = zip

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
        return render_template("radar.html", version=__version__)

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
        # Re-simulate counterfactual on demand with the cached world model
        import numpy as np  # noqa
        from netwatch.counterfactual.simulator import CounterfactualEngine
        history = pipe.states[-10:]
        engine = CounterfactualEngine(pipe.trainer.model,
                                      pipe.attack_forecaster,
                                      pipe.normalizer)
        sim = engine.simulate(history, actions=actions, k=k)
        rec = engine.recommend(sim)
        return jsonify({**sim, "recommendation": rec})

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "Not found"}), 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
