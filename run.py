"""
SIH26153 — Counterfactual Cyber World Model
Entry point for the NetWatch dashboard.

Usage:
    # Train the World Model (lazily on first dashboard request) and serve UI
    python run.py

    # Serve on a specific port
    python run.py --port 8080

    # Run the pipeline once and print a report, then exit (no web server)
    python run.py --pipeline-only

The dashboard is `netwatch/dashboard/app.py`. On first request it trains the
LSTM World Model on synthetic data and caches the result. Everything runs
offline — no cloud / external inference.
"""

import argparse
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_pipeline():
    from netwatch.pipeline import Pipeline

    pipe = Pipeline()
    info = pipe.load_data(n_traces=4, seed=42)
    tr = pipe.train()
    ev = pipe.evaluate()
    fc = pipe.forecast_and_simulate()

    report = {
        "data": info,
        "training": tr,
        "evaluation": ev,
        "forecast": {
            "current": fc["forecast"]["current"],
            "future": fc["forecast"]["future"],
            "graph": fc["graph"],
            "counterfactual": fc["counterfactual"],
            "mitre_trajectory": fc["mitre_trajectory"],
        },
    }
    out = pipe.save_report()
    logger.info("Report written to %s", out)
    return report


def start_server(port: int, with_pipeline: bool = True):
    if with_pipeline:
        try:
            run_pipeline()
        except Exception as exc:  # dashboard will (re)train lazily if needed
            logger.warning("Pre-run pipeline failed (dashboard will retry): %s", exc)
    from netwatch.dashboard.app import app

    logger.info("Starting Counterfactual Cyber World dashboard at http://localhost:%s", port)
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")


def main():
    parser = argparse.ArgumentParser(
        description="SIH26153 — Counterfactual Cyber World Model dashboard"
    )
    parser.add_argument("--pipeline-only", action="store_true",
                        help="Run the World Model pipeline once and exit")
    parser.add_argument("--no-pipeline", action="store_true",
                        help="Skip pre-running the pipeline, serve dashboard directly")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")),
                        help="Web server port (default: 5000)")
    args = parser.parse_args()

    if args.pipeline_only:
        report = run_pipeline()
        print(json.dumps(report, indent=2, default=str))
        return

    start_server(args.port, with_pipeline=not args.no_pipeline)


if __name__ == "__main__":
    main()
