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
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_dotenv(path: Path = None) -> None:
    """Minimal .env loader: KEY=VALUE lines, no shell expansion.
    Does not override existing environment variables.
    """
    path = path or Path(__file__).resolve().parent / ".env"
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            # strip surrounding quotes if present
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception as e:  # noqa: BLE001
        logger.debug("Could not load .env (%s): %s", path, e)


def _log_tshark_status() -> None:
    """Log TShark availability at startup (non-fatal)."""
    try:
        from netwatch.live.tshark_locator import detect_tshark
        from netwatch.live.config import TSHARK_PATH
        info = detect_tshark(TSHARK_PATH)
        if info.get("available"):
            logger.info(
                "TShark detected: %s (%s) — live capture available",
                info.get("version", "?"),
                info.get("path", "?"),
            )
        elif info.get("installed"):
            logger.warning(
                "TShark found at %s but capture unavailable: %s",
                info.get("path"),
                info.get("reason"),
            )
        else:
            logger.info(
                "TShark not found (offline modes: PCAP/CSV/JSONL/synthetic still work). "
                "Run scripts/check_tshark.py or scripts/setup.py to install and enable live monitoring."
            )
    except Exception as e:  # noqa: BLE001
        logger.debug("TShark startup check skipped: %s", e)


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
    from netwatch.dashboard.app import app, _ensure_prewarm

    if with_pipeline:
        try:
            _ensure_prewarm()
        except Exception as exc:  # dashboard will build the pipeline lazily if needed
            logger.warning("Pipeline prewarm failed (dashboard will retry on demand): %s", exc)

    _log_tshark_status()

    logger.info("Starting Counterfactual Cyber World dashboard at http://localhost:%s", port)
    try:
        from waitress import serve
        threads = int(os.getenv("NETWATCH_THREADS", "16"))
        logger.info("Serving via waitress (%s threads)", threads)
        serve(app, host="0.0.0.0", port=port, threads=threads,
              channel_timeout=120)
    except ImportError:
        debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
        app.run(host="0.0.0.0", port=port, debug=debug_mode, threaded=True)


def main():
    # Load .env early so env vars are available for config resolution
    _load_dotenv()

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