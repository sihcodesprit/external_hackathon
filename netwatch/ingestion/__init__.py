"""
Ingestion package: parse PCAP/CSV/JSONL telemetry.

Modules:
- parser: PCAP/CSV/JSONL ingestion
- dataset_levels: Dataset complexity levels (Level 1-6)
- datasets.adapters: Public dataset adapters (CIC-IDS, CTU-13, UNSW-NB15, CICIoT)
"""

from netwatch.ingestion.dataset_levels import (
    DATASET_LEVELS,
    DatasetLevel,
    apply_level_to_config,
    get_level,
    get_level_config,
    list_levels,
)
from netwatch.ingestion.parser import (
    PacketRecord,
    ingest,
    iter_records,
    load_flow_csv,
    load_packets_jsonl,
    load_pcap,
)

__all__ = [
    "PacketRecord",
    "load_pcap",
    "load_flow_csv",
    "load_packets_jsonl",
    "ingest",
    "iter_records",
    "DatasetLevel",
    "DATASET_LEVELS",
    "get_level",
    "list_levels",
    "get_level_config",
    "apply_level_to_config",
]
