"""
Public dataset adapters.

Each adapter converts a source dataset into the common PacketRecord / NetworkState
schema so downstream feature extraction and the World Model are dataset-agnostic.

Supported (priority per problem statement):
  1. CIC-IDS2017/2018
  2. CTU-13
  3. UNSW-NB15
  4. CICIoT2023

Only the column-mapping is implemented here. No dataset files ship with this
repo, so downstream results against these datasets are reported as
"Not evaluated yet" until real data is provided (see EXPERIMENTS.md).
"""

import logging
from pathlib import Path
from typing import List

from netwatch.ingestion.parser import PacketRecord

logger = logging.getLogger(__name__)


class DatasetAdapter:
    """Base adapter interface."""

    name = "generic"

    def load(self, path: Path) -> List[PacketRecord]:
        raise NotImplementedError


class CICIDSAdapter(DatasetAdapter):
    """
    CIC-IDS2017/2018 CSV flow records.

    Key columns (subset of the CICFlowMeter schema):
      Flow ID, Source IP, Source Port, Destination IP, Destination Port,
      Protocol, Timestamp, Flow Duration, Total Fwd Packets, Total Length of
      Fwd Packets, ... , Label
    """
    name = "cicids"

    def load(self, path: Path) -> List[PacketRecord]:
        import csv

        records: List[PacketRecord] = []
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    rec = PacketRecord(
                        timestamp=row.get("Timestamp", ""),
                        src_ip=row.get("Source IP", ""),
                        dst_ip=row.get("Destination IP", ""),
                        src_port=int(row.get("Source Port", 0) or 0),
                        dst_port=int(row.get("Destination Port", 0) or 0),
                        protocol="TCP" if row.get("Protocol") == "6" else "UDP",
                        duration=float(row.get("Flow Duration", 0) or 0) / 1e6,
                        packets=int(row.get("Total Fwd Packets", 1) or 1),
                        bytes_sent=int(row.get("Total Length of Fwd Packets", 0) or 0),
                        # store label so it can be propagated downstream
                    )
                    rec.flags = ""
                    records.append(rec)
                except Exception as e:
                    logger.debug(f"cicids row skipped: {e}")
        logger.info(f"Loaded {len(records)} flow records from {path} (CIC-IDS)")
        return records


class CTU13Adapter(DatasetAdapter):
    """CTU-13 is bidirectional flow + separate label files; map below."""
    name = "ctu13"

    def load(self, path: Path) -> List[PacketRecord]:
        import csv

        records: List[PacketRecord] = []
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f, delimiter=",")
            for row in reader:
                try:
                    rec = PacketRecord(
                        timestamp=row.get("StartTime", ""),
                        src_ip=row.get("SrcAddr", ""),
                        dst_ip=row.get("DstAddr", ""),
                        src_port=int(row.get("Sport", 0) or 0),
                        dst_port=int(row.get("Dport", 0) or 0),
                        protocol=str(row.get("Proto", "tcp") or "tcp").upper(),
                        duration=float(row.get("Dur", 0.0) or 0.0),
                        packets=int(row.get("TotPkts", 0) or 0),
                        bytes_sent=int(row.get("TotBytes", 0) or 0),
                    )
                    records.append(rec)
                except Exception as e:
                    logger.debug(f"ctu13 row skipped: {e}")
        return records


class UNSWNB15Adapter(DatasetAdapter):
    """UNSW-NB15 CSV flow records."""
    name = "unswnb15"

    def load(self, path: Path) -> List[PacketRecord]:
        import csv

        records: List[PacketRecord] = []
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    rec = PacketRecord(
                        timestamp=row.get("Stime", ""),
                        src_ip=row.get("SrcIP", ""),
                        dst_ip=row.get("DstIP", ""),
                        src_port=int(row.get("Sport", 0) or 0),
                        dst_port=int(row.get("Dport", 0) or 0),
                        protocol=str(row.get("Proto", "") or "").upper(),
                        duration=float(row.get("Dur", 0.0) or 0.0),
                        bytes_sent=int(row.get("Spkts", 0) or 0),
                    )
                    records.append(rec)
                except Exception:
                    continue
        return records


class CICIoTAdapter(DatasetAdapter):
    """CICIoT2023 CSV flow records (subset)."""
    name = "ciciot"

    def load(self, path: Path) -> List[PacketRecord]:
        import csv

        records: List[PacketRecord] = []
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    rec = PacketRecord(
                        timestamp=row.get("Timestamp", ""),
                        src_ip=row.get("Src_IP", ""),
                        dst_ip=row.get("Dst_IP", ""),
                        src_port=int(row.get("Src_Port", 0) or 0),
                        dst_port=int(row.get("Dst_Port", 0) or 0),
                        protocol=str(row.get("Protocol", "") or "").upper(),
                        duration=float(row.get("Duration", 0.0) or 0.0),
                        packets=int(row.get("Tot_Fwd_Pkts", 1) or 1),
                    )
                    records.append(rec)
                except Exception:
                    continue
        return records


ADAPTERS = {
    "cicids": CICIDSAdapter,
    "cicids2017": CICIDSAdapter,
    "cicids2018": CICIDSAdapter,
    "ctu13": CTU13Adapter,
    "unswnb15": UNSWNB15Adapter,
    "ciciot": CICIoTAdapter,
    "ciciot2023": CICIoTAdapter,
}


def get_adapter(kind: str) -> DatasetAdapter:
    if kind.lower() not in ADAPTERS:
        raise ValueError(f"Unknown dataset kind: {kind}. "
                         f"Supported: {sorted(ADAPTERS)}")
    return ADAPTERS[kind.lower()]()
