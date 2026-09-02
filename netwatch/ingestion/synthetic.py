"""
Self-contained synthetic traffic generator for development, unit testing, and
UI demonstration ONLY.

Produces realistic multi-stage attack sequences encoded as temporal packet
streams. The synthetic data is structured so the World Model can learn actual
state-transition dynamics (i.e. attack progression), not random noise.

IMPORTANT: Synthetic data is used only for development/demo. Research claims
based on synthetic data must be clearly labelled as such (see EXPERIMENTS.md).
"""

import json
import logging
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import List, Optional

from main.netwatch.ingestion.parser import PacketRecord

logger = logging.getLogger(__name__)

# MITRE kill-chain stages we model (progression order)
STAGES = [
    "Reconnaissance",
    "Initial Access",
    "Execution",
    "Lateral Movement",
    "Command and Control",
    "Exfiltration",
]

# Port per stage (approximate realism)
STAGE_PORTS = {
    "Reconnaissance": [22, 80, 443, 8080, 21, 23, 3389],
    "Initial Access": [22, 80, 443, 3389, 3306],
    "Execution": [80, 443, 8080],
    "Lateral Movement": [445, 3389, 135, 139],
    "Command and Control": [53, 80, 443, 8080, 4444],
    "Exfiltration": [80, 443, 21, 53],
}

PROTOCOLS = ["TCP", "TCP", "TCP", "UDP"]
ATTACKER_IPS = ["198.51.100.10", "198.51.100.20", "203.0.113.50"]
TARGET_IPS = ["10.0.0.10", "10.0.0.20", "10.0.1.5"]


def _ts(base: datetime, delta_sec: float) -> str:
    return (base + timedelta(seconds=delta_sec)).isoformat().replace("+00:00", "Z")


def _ts_within(rng: random.Random, base: datetime, offset_sec: float,
               span_sec: float) -> str:
    """Timestamp at `offset_sec + small jitter` from the base time (seeded)."""
    return _ts(base, offset_sec + rng.uniform(0.0, max(span_sec, 1e-3)))


def _flags_for_stage(stage: str) -> str:
    """Pick TCP flags indicative of the stage's activity."""
    if stage == "Reconnaissance":
        return random.choice(["S", "S", "SA", "R"])
    if stage in ("Initial Access", "Execution"):
        return random.choice(["S", "SA", "A", "P", "R"])
    if stage == "Lateral Movement":
        return random.choice(["S", "SA", "A", "R", "A"])
    if stage == "Command and Control":
        return random.choice(["A", "P", "PSH", "A"])
    return random.choice(["A", "P", "A", "A"])


def _payload_for_stage(stage: str) -> int:
    if stage in ("Command and Control", "Exfiltration"):
        return random.randint(200, 1500)
    if stage == "Reconnaissance":
        return random.randint(0, 80)
    return random.randint(40, 900)


def generate_trace(
    duration_minutes: float = 120.0,
    attack_bin_fraction: float = 0.25,
    packets_per_window: int = 60,
    random_seed: int = 42,
    include_stages: List[str] = None,
    time_offset_minutes: float = 0.0,
) -> List[PacketRecord]:
    """
    Generate a realistic packet stream with precise control over the
    ground-truth state profile.

    Approach (direct, robust):
      1. Build a per-30s-bin profile: each bin is benign or one MITRE stage.
      2. Attack bins are grouped into *sustained* campaigns — each campaign
         spans every stage for `STAGE_SPAN` consecutive bins (so an attack
         persists across multiple windows and stage-to-stage transitions are
         learnable). Campaigns are interleaved across the timeline so both
         classes appear in every time segment.
      3. Emit packets realizing each bin's profile (benign or stage-typed).

    `time_offset_minutes` staggers the trace on the shared clock so multiple
    traces concatenate into a longer, diverse timeline.

    Returns a flat list of PacketRecords (each tagged with ground-truth
    `label` and `stage`).
    """
    from main.netwatch.config import WINDOW_SECONDS

    rng = random.Random(random_seed)
    bg = datetime.now(UTC) + timedelta(minutes=time_offset_minutes)
    total_seconds = duration_minutes * 60.0
    n_bins = max(1, int(total_seconds // WINDOW_SECONDS))
    records: List[PacketRecord] = []

    stages = include_stages or STAGES
    n_stages = len(stages)
    STAGE_SPAN = 3  # each stage is sustained across 3 consecutive 30s bins

    # ── 1. Ground-truth bin profile ────────────────────────
    profile: List[Optional[str]] = [None] * n_bins  # None = benign
    bins_per_campaign = n_stages * STAGE_SPAN
    n_campaigns = max(1, int(n_bins * attack_bin_fraction // bins_per_campaign))
    campaign_count = 0
    for c in range(n_campaigns):
        # start bin interleaved across the timeline to keep both classes present
        start = int((c + 0.5) / max(n_campaigns, 1) * n_bins)
        bin_cursor = start
        for s_idx, stage in enumerate(stages):
            for _ in range(STAGE_SPAN):
                if 0 <= bin_cursor < n_bins:
                    profile[bin_cursor] = stage
                bin_cursor += 1
        campaign_count += 1

    n_attack_bins = sum(1 for p in profile if p is not None)
    n_normal_bins = n_bins - n_attack_bins

    # ── 2. Attack packets per stage bin (sustained burst) ──
    for bin_idx, stage in enumerate(profile):
        if stage is None:
            continue
        win_t0 = bin_idx * WINDOW_SECONDS
        src = ATTACKER_IPS[bin_idx % len(ATTACKER_IPS)]
        dst = TARGET_IPS[bin_idx % len(TARGET_IPS)]
        burst = int(packets_per_window * 5)
        for _ in range(burst):
            records.append(PacketRecord(
                timestamp=_ts_within(rng, bg, win_t0, WINDOW_SECONDS),
                src_ip=src,
                dst_ip=dst,
                src_port=rng.choice([1024, 2048, 3333, 4444, 51234]),
                dst_port=rng.choice(STAGE_PORTS[stage]),
                protocol=rng.choice(PROTOCOLS),
                flags=_flags_for_stage(stage),
                bytes_sent=_payload_for_stage(stage),
                packets=1,
                ttl=rng.randint(50, 64),
                payload_size=_payload_for_stage(stage),
                tcp_window=rng.randint(29200, 65535),
                duration=rng.uniform(0.001, 0.5),
                label=1,
                stage=stage,
            ))

    # ── 3. Normal packets per benign bin ───────────────────
    for bin_idx, stage in enumerate(profile):
        if stage is not None:
            continue
        win_t0 = bin_idx * WINDOW_SECONDS
        src = f"{rng.randint(11, 199)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"
        dst = rng.choice(TARGET_IPS)
        for _ in range(packets_per_window):
            records.append(PacketRecord(
                timestamp=_ts_within(rng, bg, win_t0, WINDOW_SECONDS),
                src_ip=src,
                dst_ip=dst,
                src_port=rng.randint(30000, 60000),
                dst_port=rng.choice([80, 443, 53]),
                protocol=rng.choice(PROTOCOLS),
                flags="A",
                bytes_sent=rng.randint(200, 1400),
                packets=1,
                ttl=rng.randint(55, 64),
                payload_size=rng.randint(200, 1400),
                tcp_window=rng.randint(29200, 65535),
                duration=rng.uniform(0.001, 0.5),
                label=0,
            ))

    records.sort(key=lambda r: r.timestamp)
    logger.info(f"Synthetic generator: {n_attack_bins} attack bins / "
                f"{n_normal_bins} normal bins ({campaign_count} campaigns)")
    return records


def save_records(records: List[PacketRecord], path: Path):
    from main.netwatch.ingestion.parser import iter_records

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for d in iter_records(records):
            f.write(json.dumps(d) + "\n")
    logger.info(f"Saved {len(records)} packet records to {path}")
    return len(records)
