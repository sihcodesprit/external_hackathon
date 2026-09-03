#!/usr/bin/env python
"""
Forecast from CSV/JSONL file.

Usage:
    python forecast.py --input data.csv --horizon 5
    python forecast.py --input data.jsonl --horizon 10 --model data/models/world_model_lstm.pt

Loads a trained World Model and runs K-step forecasting on the provided data.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

from netwatch.config import ensure_dirs
from netwatch.features.network_state import StateBuilder
from netwatch.features.sequences import StateNormalizer, build_sequences
from netwatch.forecasting.attack_forecaster import AttackForecaster
from netwatch.forecasting.stage_predictor import StagePredictor
from netwatch.graph.predictive_attack_graph import build_predictive_graph
from netwatch.ingestion.parser import ingest
from netwatch.models.lstm_world_model import LSTMWorldModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def load_model_and_scaler(model_path: str, scaler_path: str):
    """Load trained model and scaler."""
    model = LSTMWorldModel()
    if not model.load(model_path):
        raise FileNotFoundError(f"Model not found at {model_path}")
    
    normalizer = StateNormalizer.load(scaler_path)
    return model, normalizer


def process_input_file(input_path: Path):
    """Ingest and build states from input file."""
    logger.info(f"Ingesting {input_path}...")
    records = ingest(input_path)
    
    if not records:
        raise ValueError(f"No valid records found in {input_path}")
    
    logger.info(f"Loaded {len(records)} records")
    
    # Build states
    builder = StateBuilder(group_by_pair=False)
    states = builder.build_states(records)
    
    if not states:
        raise ValueError("No valid network states could be generated")
    
    logger.info(f"Built {len(states)} network states")
    return states


def run_forecast(states, model, normalizer, horizon: int, sequence_length: int = 10):
    """Run K-step forecast on the most recent states."""
    # Normalize states
    norm_states = [normalizer.transform(s) for s in states]
    
    # Check we have enough history
    if len(norm_states) < sequence_length:
        raise ValueError(f"Need at least {sequence_length} states, got {len(norm_states)}")
    
    # Use last sequence_length states as history
    history = norm_states[-sequence_length:]
    raw_history = states[-sequence_length:]
    
    # Create forecaster
    forecaster = AttackForecaster(model, normalizer, StagePredictor())
    # Note: risk head won't be trained without labels, will use magnitude fallback
    
    # Run forecast
    forecast = forecaster.forecast(raw_history, k=horizon)
    
    # Build predictive graph
    graph = build_predictive_graph(forecast)
    
    return forecast, graph


def print_forecast(forecast, graph):
    """Print forecast results in a readable format."""
    current = forecast["current"]
    future = forecast["future"]
    
    print("\n" + "=" * 60)
    print("NETWORK ATTACK FORECAST")
    print("=" * 60)
    
    print(f"\nCURRENT STATE (t)")
    print(f"  Risk:       {current['risk']*100:.1f}%")
    print(f"  Stage:      {current['stage']}")
    print(f"  Confidence: {current.get('confidence', 0)*100:.1f}%")
    
    print(f"\nFUTURE FORECAST ({len(future)} steps)")
    print("-" * 60)
    print(f"{'Step':<6} {'Window':<8} {'Risk':<10} {'Stage':<25} {'Conf':<8}")
    print("-" * 60)
    for step in future:
        print(f"{step['step']:<6} {step['window']:<8} {step['risk']*100:>6.1f}%  "
              f"{step['stage']:<25} {step.get('confidence', 0)*100:>6.1f}%")
    
    print("\nPREDICTIVE ATTACK GRAPH")
    print("-" * 60)
    for node in graph["nodes"]:
        print(f"  Node: {node['label']} (severity: {node['severity']}, risk: {node['risk']:.2f})")
    for edge in graph["edges"]:
        print(f"  Edge: {edge['source']} -> {edge['target']} (weight: {edge['weight']:.3f})")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Run K-step attack forecast on network traffic data")
    parser.add_argument("--input", "-i", required=True, help="Input file (CSV, JSONL, or PCAP)")
    parser.add_argument("--horizon", "-k", type=int, default=5, help="Forecast horizon (default: 5)")
    parser.add_argument("--model", "-m", default="data/models/world_model_lstm.pt", 
                        help="Path to trained model (default: data/models/world_model_lstm.pt)")
    parser.add_argument("--scaler", "-s", default="data/models/feature_scaler.pkl",
                        help="Path to feature scaler (default: data/models/feature_scaler.pkl)")
    parser.add_argument("--sequence-length", "-l", type=int, default=10,
                        help="Sequence length for world model (default: 10)")
    parser.add_argument("--output", "-o", help="Output JSON file for results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    ensure_dirs()
    
    # Check files exist
    model_path = Path(args.model)
    scaler_path = Path(args.scaler)
    input_path = Path(args.input)
    
    if not model_path.exists():
        logger.error(f"Model not found: {model_path}")
        logger.error("Train a model first with: python run.py --pipeline-only")
        sys.exit(1)
    
    if not scaler_path.exists():
        logger.error(f"Scaler not found: {scaler_path}")
        sys.exit(1)
    
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)
    
    try:
        # Load model and scaler
        logger.info(f"Loading model from {model_path}")
        model, normalizer = load_model_and_scaler(str(model_path), str(scaler_path))
        
        # Process input
        states = process_input_file(input_path)
        
        # Run forecast
        forecast, graph = run_forecast(states, model, normalizer, args.horizon, args.sequence_length)
        
        # Print results
        print_forecast(forecast, graph)
        
        # Save to file if requested
        if args.output:
            output_data = {
                "forecast": forecast,
                "graph": graph,
            }
            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2, default=str)
            logger.info(f"Results saved to {args.output}")
        
    except Exception as e:
        logger.error(f"Forecast failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()