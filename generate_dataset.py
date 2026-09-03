#!/usr/bin/env python3
"""
Generate a 10K packet dataset using the synthetic traffic generator (fast).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from netwatch.ingestion.synthetic import generate_trace, save_records
from netwatch.config import GENERATED_DIR, ensure_dirs


def main():
    ensure_dirs()
    
    # Fast generation: use larger packets_per_window to hit ~10K in one call
    # duration_minutes=40 -> 80 bins, attack_bin_fraction=0.25 -> 20 attack bins, 60 normal bins
    # packets_per_window=80 -> 20*400 + 60*80 = 8000 + 4800 = 12800 packets
    
    records = generate_trace(
        duration_minutes=40.0,
        attack_bin_fraction=0.25,
        packets_per_window=80,
        random_seed=42,
    )
    
    # Truncate to exactly 10K
    records = records[:10000]
    print(f"Generated {len(records)} packet records")
    
    output_path = GENERATED_DIR / "packets_10k.jsonl"
    save_records(records, output_path)
    print(f"Dataset saved to {output_path}")
    
    # Quick verify
    attack_count = sum(1 for r in records if r.label == 1)
    normal_count = len(records) - attack_count
    stages = set(r.stage for r in records if r.stage)
    print(f"Attack packets: {attack_count}")
    print(f"Normal packets: {normal_count}")
    print(f"Attack stages present: {stages}")


if __name__ == "__main__":
    main()