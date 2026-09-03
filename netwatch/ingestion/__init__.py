"""
Ingestion package: parse PCAP/CSV/JSONL telemetry and generate synthetic traffic.

Modules:
- parser: PCAP/CSV/JSONL ingestion
- synthetic: Synthetic traffic generator
- dataset_levels: Dataset complexity levels (Level 1-6)
- datasets.adapters: Public dataset adapters (CIC-IDS, CTU-13, UNSW-NB15, CICIoT)
"""

from netwatch.ingestion.parser import (
    PacketRecord,
    load_pcap,
    load_flow_csv,
    load_packets_jsonl,
    ingest,
    iter_records,
)
from netwatch.ingestion.synthetic import generate_trace, save_records
from netwatch.ingestion.dataset_levels import (
    DatasetLevel,
    DATASET_LEVELS,
    get_level,
    list_levels,
    get_level_config,
    apply_level_to_config,
)

__all__ = [
    "PacketRecord",
    "load_pcap",
    "load_flow_csv",
    "load_packets_jsonl",
    "ingest",
    "iter_records",
    "generate_trace",
    "save_records",
    "DatasetLevel",
    "DATASET_LEVELS",
    "get_level",
    "list_levels",
    "get_level_config",
    "apply_level_to_config",
]