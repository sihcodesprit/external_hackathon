"""
Sandbox Scenario Runner.

Loads scenario definitions from sandbox/scenarios/*.json and runs them through
the NetWatch pipeline, producing per-scenario reports with forecast, counterfactual,
MITRE mapping, and entity resolution results.

Usage:
    python -m sandbox.runner --scenario recon
    python -m sandbox.runner --scenario mixed --k 10
    python -m sandbox.runner --all
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def load_scenario(name: str) -> dict:
    path = SCENARIOS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario '{name}' not found at {path}")
    with open(path) as f:
        return json.load(f)


def list_scenarios() -> list:
    return [p.stem for p in sorted(SCENARIOS_DIR.glob("*.json"))]


def run_scenario(scenario: dict, k: int = 5) -> dict:
    from netwatch.pipeline import Pipeline

    synth = scenario.get("synthetic_config", {})
    n_traces = synth.get("n_traces", 4)
    seed = synth.get("seed", 42)
    duration = synth.get("duration_minutes", 30)
    attack_types = synth.get("attack_types", [])

    pipe = Pipeline()
    data_info = pipe.load_data(
        n_traces=n_traces,
        seed=seed,
        duration_minutes=duration,
        attack_types=attack_types,
    )
    train_info = pipe.train()
    eval_info = pipe.evaluate()
    forecast_info = pipe.forecast_and_simulate(k=k)

    return {
        "scenario": scenario.get("name"),
        "description": scenario.get("description"),
        "difficulty": scenario.get("difficulty"),
        "attack_types": scenario.get("attack_types"),
        "mitre_phases": scenario.get("mitre_phases"),
        "data": data_info,
        "training": train_info,
        "evaluation": eval_info,
        "forecast": forecast_info.get("forecast", {}),
        "counterfactual": forecast_info.get("counterfactual", {}),
        "mitre_trajectory": forecast_info.get("mitre_trajectory", []),
        "network_topology": forecast_info.get("network_topology", {}),
        "entity_summary": forecast_info.get("entity_summary", {}),
    }


def main():
    parser = argparse.ArgumentParser(description="Run sandbox scenarios")
    parser.add_argument("--scenario", type=str, help="Scenario name to run")
    parser.add_argument("--all", action="store_true", help="Run all scenarios")
    parser.add_argument("--k", type=int, default=5, help="Forecast horizon")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    parser.add_argument("--output", type=str, help="Output directory for reports")
    args = parser.parse_args()

    if args.list:
        for name in list_scenarios():
            print(f"  - {name}")
        return

    scenarios_to_run = []
    if args.all:
        scenarios_to_run = list_scenarios()
    elif args.scenario:
        scenarios_to_run = [args.scenario]
    else:
        print("Specify --scenario NAME or --all or --list")
        return

    output_dir = Path(args.output) if args.output else Path("data") / "sandbox_reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    for name in scenarios_to_run:
        print(f"\n{'='*60}")
        print(f"Running scenario: {name}")
        print(f"{'='*60}")
        try:
            scenario = load_scenario(name)
            result = run_scenario(scenario, k=args.k)
            report_path = output_dir / f"scenario_{name}.json"
            report_path.write_text(json.dumps(result, default=str, indent=2))
            print(f"  Report saved: {report_path}")
            fc = result.get("forecast", {})
            current = fc.get("current", {})
            print(f"  Current risk: {current.get('risk', 'N/A')}")
            print(f"  Current stage: {current.get('stage', 'N/A')}")
            rec = result.get("counterfactual", {}).get("recommendation", {})
            print(f"  Recommended action: {rec.get('recommended_label', 'N/A')}")
            print(f"  Risk reduction: {rec.get('risk_reduction_pct_points', 'N/A')}%")
        except Exception as e:
            print(f"  ERROR: {e}")
            logger.exception(f"Failed scenario {name}")


if __name__ == "__main__":
    main()
