"""
Document assembly for the dashboard.

Builds the single JSON "analysis document" consumed by every frontend screen.
Every metric is computed from real pipeline/model output — nothing is fabricated.
"""

import logging
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from netwatch.features.entropy_features import shannon_entropy
from netwatch.features.network_state import NetworkState

logger = logging.getLogger(__name__)

# Feature grouping keyed to the groups actually produced by StateBuilder
_TRAFFIC_KEYS = [
    "bytes", "packets", "ttl_mean", "payload_mean", "payload_max", "tcp_window_mean",
    "packets_per_second", "connection_rate", "unique_dst_ports", "unique_dst_hosts",
    "syn_rate", "ack_rate", "rst_rate", "syn_ack_ratio", "port_entropy",
]
_TCP_KEYS = [
    "syn_count", "syn_ack_count", "ack_count", "rst_count", "fin_count",
    "syn_ack_ratio", "syn_synack_ratio", "rst_syn_ratio", "half_open_ratio",
    "ack_completion_ratio", "delta_syn_rate", "delta_syn_ack_ratio",
    "delta_half_open_ratio", "delta_rst_rate",
]
_ENTROPY_KEYS = [
    "src_port_entropy", "dst_port_entropy", "protocol_entropy", "src_ip_entropy",
    "dst_ip_entropy", "payload_size_entropy", "packet_size_entropy", "tcp_flag_entropy",
    "port_entropy_delta", "port_entropy_acceleration", "dst_entropy_delta",
    "dst_entropy_acceleration", "payload_entropy_delta", "payload_entropy_acceleration",
]
_TEMPORAL_KEYS = [
    "iat_mean", "iat_std", "iat_variance", "iat_cv", "iat_min", "iat_max",
    "iat_autocorr", "periodicity_score", "burstiness", "fft_dominant_freq",
    "fft_spectral_power",
]
_GRAPH_KEYS = [
    "node_count", "edge_count", "graph_density", "average_degree", "degree_variance",
    "clustering_coefficient", "new_edges", "removed_edges", "new_destinations",
    "new_sources", "eigenvector_centrality_max", "betweenness_centrality_max",
    "pagerank_max", "new_edges_rate", "new_destinations_rate",
    "density_delta", "avg_degree_delta", "node_count_delta", "edge_count_delta",
]

_GROUP_DEFS = [
    ("traffic", _TRAFFIC_KEYS, "Flow, packet and timing volume features."),
    ("tcp_handshake", _TCP_KEYS, "TCP handshake completion and asymmetry features."),
    ("entropy", _ENTROPY_KEYS, "Shannon entropy of ports, IPs, sizes and flags."),
    ("temporal", _TEMPORAL_KEYS, "Inter-arrival time, jitter and burstiness features."),
    ("graph", _GRAPH_KEYS, "Dynamic graph topology and connectivity features."),
]

_METRIC_LABELS = {
    "packets_per_second": "Packet Rate (pkts/s)",
    "connection_rate": "Connection Rate (/s)",
    "unique_dst_ports": "Unique Destination Ports",
    "unique_dst_hosts": "Unique Destination Hosts",
    "syn_rate": "SYN Rate (/s)",
    "ack_rate": "ACK Rate (/s)",
    "rst_rate": "RST Rate (/s)",
    "syn_ack_ratio": "SYN/ACK Ratio",
    "port_entropy": "Port Entropy",
    "bytes": "Bytes",
    "packets": "Packets",
    "ttl_mean": "Mean TTL",
    "payload_mean": "Mean Payload (B)",
    "tcp_window_mean": "Mean TCP Window",
    "dst_port_entropy": "Destination Port Entropy",
    "dst_ip_entropy": "Destination IP Entropy",
    "protocol_entropy": "Protocol Entropy",
    "tcp_flag_entropy": "TCP Flag Entropy",
    "payload_size_entropy": "Payload Size Entropy",
    "packet_size_entropy": "Packet Size Entropy",
    "iat_mean": "Mean Inter-Arrival (ms)",
    "iat_std": "IAT Std (ms)",
    "burstiness": "Burstiness",
    "periodicity_score": "Periodicity",
    "graph_density": "Graph Density",
    "average_degree": "Average Degree",
    "node_count": "Graph Nodes",
    "edge_count": "Graph Edges",
    "new_destinations": "New Destinations",
    "syn_count": "SYN Count",
    "syn_ack_count": "SYN-ACK Count",
    "ack_count": "ACK Count",
    "rst_count": "RST Count",
    "fin_count": "FIN Count",
    "half_open_ratio": "Half-Open Ratio",
}


def _safe(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if math.isnan(f) or math.isinf(f):
        return default
    return f


def _parse_ts(ts_str: str):
    if isinstance(ts_str, datetime):
        return ts_str
    s = str(ts_str).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    try:
        return datetime.fromtimestamp(float(s))
    except (ValueError, OverflowError, OSError):
        return None


def build_traffic_summary(records: List[Any], states: Optional[List[NetworkState]] = None) -> Dict[str, Any]:
    """Aggregate real packet/flow statistics from the ingested records."""
    protocols = Counter()
    src_hosts: set = set()
    dst_hosts: set = set()
    all_hosts: set = set()
    dst_ports: set = set()
    flows: set = set()
    attack_labels = 0
    stages = Counter()
    total_bytes = 0
    ts_min = None
    ts_max = None

    for r in records:
        protocol = getattr(r, "protocol", None) or (r.get("protocol") if isinstance(r, dict) else None)
        src_ip = getattr(r, "src_ip", None) or (r.get("src_ip") if isinstance(r, dict) else None)
        dst_ip = getattr(r, "dst_ip", None) or (r.get("dst_ip") if isinstance(r, dict) else None)
        dst_port = getattr(r, "dst_port", None) or (r.get("dst_port") if isinstance(r, dict) else None)
        label = getattr(r, "label", 0) or 0
        stage = getattr(r, "stage", None) or (r.get("stage") if isinstance(r, dict) else None)
        bytes_sent = getattr(r, "bytes_sent", 0) or (r.get("bytes_sent", 0) if isinstance(r, dict) else 0)
        ts = getattr(r, "timestamp", None) or (r.get("timestamp") if isinstance(r, dict) else None)
        parsed_ts = _parse_ts(ts)

        if protocol:
            protocols[str(protocol).upper()] += 1
        if src_ip:
            src_hosts.add(src_ip)
        if dst_ip:
            dst_hosts.add(dst_ip)
        if dst_ip:
            all_hosts.add(dst_ip)
        if src_ip:
            all_hosts.add(src_ip)
        if dst_port:
            dst_ports.add(int(dst_port))
        if src_ip and dst_ip:
            flows.add((src_ip, dst_ip, dst_port, protocol))
        if int(label or 0) == 1:
            attack_labels += 1
            if stage:
                stages[str(stage)] += 1
        total_bytes += int(bytes_sent or 0)

        if parsed_ts:
            ts_min = min(ts_min, parsed_ts) if ts_min else parsed_ts
            ts_max = max(ts_max, parsed_ts) if ts_max else parsed_ts

    duration = (ts_max - ts_min).total_seconds() if ts_min and ts_max else 0.0

    attack_states = 0
    benign_states = 0
    for s in states or []:
        if int(s.label or 0) == 1:
            attack_states += 1
        else:
            benign_states += 1

    return {
        "n_packets": len(records),
        "n_bytes": total_bytes,
        "n_flows": len(flows),
        "n_hosts": len(all_hosts),
        "n_src_hosts": len(src_hosts),
        "n_dst_hosts": len(dst_hosts),
        "n_unique_ports": len(dst_ports),
        "duration_seconds": round(duration, 2),
        "protocols": [{"protocol": p, "count": c} for p, c in protocols.most_common()],
        "attack_packets": attack_labels,
        "benign_packets": len(records) - attack_labels,
        "attack_states": attack_states,
        "benign_states": benign_states,
        "stages_present": [{"stage": s, "count": c} for s, c in stages.most_common()],
    }


def build_network_state_payload(states: List[NetworkState]) -> Dict[str, Any]:
    """Timeline of windowed network states with grouped feature vectors."""
    rows: List[Dict[str, Any]] = []
    for i, s in enumerate(states):
        features = dict(s.features or {})
        groups = defaultdict(dict)

        # Build human-friendly grouped metrics for display
        for group_name, keys, _desc in _GROUP_DEFS:
            for k in keys:
                if k in features:
                    groups[group_name][k] = _safe(features[k])

        # Stable ordering per row
        row: Dict[str, Any] = {
            "idx": i,
            "timestamp": s.timestamp,
            "label": int(s.label or 0),
            "stage": s.stage or "",
        }
        for group_name, _, _desc in _GROUP_DEFS:
            row[group_name] = dict(groups[group_name])
        row["other"] = {
            k: _safe(v) for k, v in features.items()
            if k not in set(_TRAFFIC_KEYS + _TCP_KEYS + _ENTROPY_KEYS + _TEMPORAL_KEYS + _GRAPH_KEYS + ["timestamp"])
        }
        rows.append(row)

    return {
        "count": len(rows),
        "groups": [{"id": gid, "label": gid.replace("_", " ").title(), "description": desc}
                   for gid, _k, desc in _GROUP_DEFS],
        "metric_labels": _METRIC_LABELS,
        "states": rows,
    }


def _group_features(features: Dict[str, float]) -> List[Dict[str, Any]]:
    groups = []
    for group_name, keys, desc in _GROUP_DEFS:
        present = [{"feature": k, "label": _METRIC_LABELS.get(k, k.replace("_", " ").title().capitalize()),
                    "value": _safe(features.get(k))} for k in keys if k in features]
        if present:
            groups.append({"id": group_name, "label": group_name.replace("_", " ").title(),
                           "description": desc, "features": present})
    return groups


def analyze_records(records: List[Any], filename: str, member: Optional[str] = None,
                    source_label: str = "User Uploaded PCAP",
                    occurrence: Optional[str] = None,
                    progress_fn=None,
                    pipeline_factory=None) -> Dict[str, Any]:
    """Run the full pipeline on ingested records and return the complete analysis document."""
    started = datetime.now()

    def tick(stage: str, progress: int, message: str):
        if progress_fn:
            progress_fn(stage, progress, message)

    tick("Packet parsing", 8, "Normalized packet records.")
    if not records:
        return {"error": "No valid packet or flow records found."}

    from netwatch.pipeline import Pipeline
    pipe = pipeline_factory() if pipeline_factory else Pipeline()
    tick("Network State", 18, "Building temporal network states.")
    data_info = pipe.load_data(records=records)
    states = pipe.states
    if not states:
        return {"error": "Traffic was parsed, but not enough temporal windows could be formed to build network states."}

    # Train the world model + scaler entirely on THIS capture (in-memory,
    # persist=False → no dataset/model files are written to disk).
    tick("World Model training", 32, "Training world model on this capture.")
    try:
        pipe.train(persist=False, model_type="linear")
    except Exception as e:  # noqa: BLE001
        return {"error": f"Could not train the world model on this capture: {e}"}

    tick("World Model forecast", 44, "Rolling out world model K-step predictions.")
    sim_out = pipe.forecast_and_simulate(k=5)
    forecast = sim_out["forecast"]
    graph = sim_out["graph"]
    counterfactual = sim_out["counterfactual"]
    mitre = sim_out.get("mitre_trajectory", [])

    tick("Ensemble analysis", 62, "Running 8 detection engines.")
    from netwatch.forecasting.ensemble_scorer import EnsembleScorer
    scorer = EnsembleScorer(pipeline=pipe)
    ensemble_res = scorer.evaluate_traffic(records=records, states=states, k_steps=5)

    tick("Collecting metrics", 86, "Assembling analysis document.")
    doc = {
        "status": "ok",
        "type": "traffic_data",
        "filename": filename,
        "member": member,
        "source": source_label,
        "occurrence": occurrence,
        "n_records": len(records),
        "n_states": len(states),
        "traffic_summary": build_traffic_summary(records, states),
        "network_state": build_network_state_payload(states),
        "forecast": forecast,
        "graph": graph,
        "counterfactual": counterfactual,
        "mitre_trajectory": mitre,
        "ensemble": ensemble_res,
        "topology": sim_out.get("network_topology", {}),
        "entities": sim_out.get("entity_summary", {}),
        "state_groups": _group_features(states[-1].features) if states else [],
        "data_info": data_info,
        "started_at": started.isoformat(),
        "finished_at": datetime.now().isoformat(),
    }
    tick("Analysis complete", 100, "Results ready.")
    return doc


def build_document_from_pipeline(
    pipe,
    records: List[Any],
    filename: str,
    member: Optional[str] = None,
    source_label: str = "User Uploaded PCAP",
    occurrence: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble the canonical analysis document from an already-trained pipeline.

    Used when a Model Test Center "Run All Modules" pass finishes: the pipeline
    already holds trained states + forecast results, so this rebuilds the same
    document shape every other screen consumes (Overview, Forecast, Attack
    Graph, MITRE, Explainability, Counterfactual) — without re-training or
    re-ingesting the capture.
    """
    started = datetime.now()
    states = getattr(pipe, "states", []) or []
    forecast = {}
    graph = {}
    counterfactual = {}
    mitre: List[Dict[str, Any]] = []
    topology = {}
    entity_summary = {}
    if getattr(pipe, "results", None):
        fr = pipe.results.get("forecast", {}) or {}
        if isinstance(fr, dict):
            forecast = fr.get("forecast", {}) or {}
            graph = fr.get("graph", {}) or {}
            counterfactual = fr.get("counterfactual", {}) or {}
            mitre = fr.get("mitre_trajectory", []) or []
            topology = fr.get("network_topology", {}) or {}
            entity_summary = fr.get("entity_summary", {}) or {}

    ensemble_res = {}
    try:
        from netwatch.forecasting.ensemble_scorer import EnsembleScorer
        scorer = EnsembleScorer(pipeline=pipe)
        ensemble_res = scorer.evaluate_traffic(records=records, states=states, k_steps=5)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not evaluate ensemble for reassembled analysis: %s", e)

    n_attack = sum(1 for s in states if int(s.label or 0) == 1)
    resolver = getattr(pipe, "entity_resolver", None)
    net_graph = getattr(pipe, "network_graph", None)
    data_info = {
        "n_packets": len(records),
        "n_states": len(states),
        "n_attack_states": n_attack,
        "n_benign_states": len(states) - n_attack,
        "n_entities": len(resolver.entities) if resolver else 0,
        "n_graph_nodes": len(net_graph.nodes) if net_graph else 0,
        "n_graph_edges": len(net_graph.edges) if net_graph else 0,
    }

    return {
        "status": "ok",
        "type": "traffic_data",
        "filename": filename,
        "member": member,
        "source": source_label,
        "occurrence": occurrence,
        "n_records": len(records),
        "n_states": len(states),
        "traffic_summary": build_traffic_summary(records, states),
        "network_state": build_network_state_payload(states),
        "forecast": forecast,
        "graph": graph,
        "counterfactual": counterfactual,
        "mitre_trajectory": mitre,
        "ensemble": ensemble_res,
        "topology": topology,
        "entities": entity_summary,
        "state_groups": _group_features(states[-1].features) if states else [],
        "data_info": data_info,
        "started_at": started.isoformat(),
        "finished_at": datetime.now().isoformat(),
    }


def _det_stats(records):
    flags = Counter()
    syn = ack = synack = rst = fin = 0
    for r in records:
        f = (getattr(r, "flags", None) or (r.get("flags", "") if isinstance(r, dict) else "") or "").upper()
        flags[f or "NOSET"] += 1
        if "S" in f:
            syn += 1
        if "A" in f:
            ack += 1
        if "S" in f and "A" in f:
            synack += 1
        if "R" in f:
            rst += 1
        if "F" in f:
            fin += 1
    return {"syn": syn, "ack": ack, "synack": synack, "rst": rst, "fin": fin,
            "half_open": max(0, syn - synack), "flag_distribution": dict(flags)}


def run_module_test(module: str, pipeline, records) -> Dict[str, Any]:
    """Run an individual pipeline module test against real current data."""
    states = getattr(pipeline, "states", []) or []
    forecast = (pipeline.results.get("forecast", {}) or {}).get("forecast", {}) if pipeline.results else {}

    if not records and not states:
        return {"status": "error", "module": module,
                "message": f"No analysis data loaded. Upload a PCAP or run a scenario first to test the {module} module."}

    try:
        if module == "packet_features":
            ttls, payloads, windows = [], [], []
            for r in records:
                t = getattr(r, "ttl", None)
                p = getattr(r, "payload_size", None)
                w = getattr(r, "tcp_window", None)
                if t:
                    ttls.append(float(t))
                if p:
                    payloads.append(float(p))
                if w:
                    windows.append(float(w))
            return {"status": "ok", "module": module,
                    "metrics": {
                        "packets": len(records),
                        "ttl_mean": round(statistics.mean(ttls), 2) if ttls else 0.0,
                        "ttl_variance": round(statistics.pstdev(ttls) ** 2, 2) if len(ttls) > 1 else 0.0,
                        "payload_size_mean": round(statistics.mean(payloads), 2) if payloads else 0.0,
                        "payload_size_max": round(max(payloads), 2) if payloads else 0.0,
                        "tcp_window_mean": round(statistics.mean(windows), 2) if windows else 0.0,
                    }}

        if module == "flow_features":
            flows = set()
            for r in records:
                flows.add((getattr(r, "src_ip", ""), getattr(r, "dst_ip", ""),
                           getattr(r, "dst_port", 0), getattr(r, "protocol", "")))
            return {"status": "ok", "module": module,
                    "metrics": {"n_flows": len(flows), "n_packets": len(records),
                                "flows_per_packet_ratio": round(len(flows) / max(len(records), 1), 4)}}

        if module == "tcp_features":
            d = _det_stats(records)
            denom = max(d["ack"], 1)
            return {"status": "ok", "module": module,
                    "metrics": {
                        "syn_count": d["syn"], "syn_ack_count": d["synack"], "ack_count": d["ack"],
                        "rst_count": d["rst"], "fin_count": d["fin"],
                        "half_open_connections": d["half_open"],
                        "syn_ack_ratio": round(d["syn"] / denom, 2),
                        "rst_syn_ratio": round(d["rst"] / max(d["syn"], 1), 2),
                        "half_open_ratio": round(d["half_open"] / max(d["syn"] + d["ack"], 1), 2),
                    },
                    "distribution": d["flag_distribution"]}

        if module == "entropy":
            ports, srcs, dsts, protocols, sizes = [], [], [], [], []
            for r in records:
                if getattr(r, "dst_port", None):
                    ports.append(int(r.dst_port))
                if getattr(r, "src_ip", None):
                    srcs.append(r.src_ip)
                if getattr(r, "dst_ip", None):
                    dsts.append(r.dst_ip)
                protocols.append(getattr(r, "protocol", ""))
                sizes.append(getattr(r, "payload_size", 0) or 0)
            return {"status": "ok", "module": module,
                    "metrics": {
                        "dst_port_entropy": round(shannon_entropy(ports), 3),
                        "src_ip_entropy": round(shannon_entropy(srcs), 3),
                        "dst_ip_entropy": round(shannon_entropy(dsts), 3),
                        "protocol_entropy": round(shannon_entropy(protocols), 3),
                        "payload_size_entropy": round(shannon_entropy(sizes), 3),
                        "unique_dst_ports": len(set(ports)),
                    }}

        if module == "temporal":
            tss = [_parse_ts(getattr(r, "timestamp", "") or (r.get("timestamp", "") if isinstance(r, dict) else ""))
                   for r in records]
            tss = [t for t in tss if t is not None]
            iats = []
            if len(tss) > 1:
                iats = [(tss[i + 1] - tss[i]).total_seconds() * 1000 for i in range(len(tss) - 1)]
            return {"status": "ok", "module": module,
                    "metrics": {
                        "iat_mean_ms": round(statistics.mean(iats), 3) if iats else 0.0,
                        "iat_std_ms": round(statistics.pstdev(iats), 3) if len(iats) > 1 else 0.0,
                        "iat_min_ms": round(min(iats), 3) if iats else 0.0,
                        "iat_max_ms": round(max(iats), 3) if iats else 0.0,
                        "burstiness": round((statistics.pstdev(iats) / max(statistics.mean(iats), 1e-6)), 3) if iats and len(iats) > 1 else 0.0,
                        "n_intervals": len(iats),
                    }}

        if module == "graph":
            topo = (pipeline.results.get("forecast", {}) or {}).get("network_topology", {})
            nodes = topo.get("nodes", []) or []
            edges = topo.get("edges", []) or []
            n = max(len(nodes), 1)
            degree_total = sum(int(g.get("degree", 0) or 0) for g in nodes)
            return {"status": "ok", "module": module,
                    "metrics": {
                        "nodes": len(nodes), "edges": len(edges),
                        "graph_density": round((2 * len(edges)) / (n * (n - 1)), 4) if n > 1 else 0.0,
                        "average_degree": round(degree_total / n, 2),
                        "edge_count_ratio": round(len(edges) / max(n - 1, 1), 3),
                    }}

        if module == "network_state":
            if not states:
                return {"status": "error", "module": module, "message": "No network states available."}
            last = states[-1]
            return {"status": "ok", "module": module,
                    "metrics": {"n_states": len(states),
                                "last_timestamp": last.timestamp,
                                "last_label": int(last.label or 0),
                                "last_stage": last.stage or "Benign",
                                "n_features": len(last.features or {})}}

        if module in ("world_model", "forecasting", "mitre", "explainability",
                      "attack_graph", "counterfactual", "recommendation"):
            current = forecast.get("current", {}) if forecast else {}
            future = forecast.get("future", []) if forecast else []
            if module == "world_model":
                return {"status": "ok", "module": module,
                        "metrics": {"current_risk": round(float(current.get("risk", 0)), 4),
                                    "projected_peak_risk": round(max([float(current.get("risk", 0))] + [float(s.get("risk", 0)) for s in future]), 4),
                                    "k_steps": len(future),
                                    "current_stage": current.get("stage", "Benign"),
                                    "future_stages": [s.get("stage") for s in future]}}
            if module == "forecasting":
                return {"status": "ok", "module": module,
                        "steps": [{"step": s.get("step"), "risk": round(float(s.get("risk", 0)), 4),
                                   "stage": s.get("stage", ""), "confidence": round(float(s.get("confidence", 0)), 3)}
                                  for s in future]}
            if module == "mitre":
                traj = (pipeline.results.get("forecast", {}) or {}).get("mitre_trajectory", [])
                return {"status": "ok", "module": module, "trajectory": traj}
            if module == "explainability":
                return {"status": "ok", "module": module,
                        "current": current.get("explanation", {}),
                        "temporal": forecast.get("temporal_explanation", {})}
            if module == "attack_graph":
                g = (pipeline.results.get("forecast", {}) or {}).get("graph", {})
                return {"status": "ok", "module": module, "graph": g}
            if module == "counterfactual" or module == "recommendation":
                cf = (pipeline.results.get("forecast", {}) or {}).get("counterfactual", {})
                return {"status": "ok", "module": module,
                        "counterfactual": cf.get("results", {}),
                        "recommendation": cf.get("recommendation", {})}

        if module == "full_pipeline":
            return {"status": "ok", "module": module,
                    "metrics": {"n_records": len(records), "n_states": len(states),
                                "forecast_ready": bool(forecast),
                                "ensemble_ready": bool(pipeline.results.get("evaluation", {}))}}

        return {"status": "error", "module": module, "message": f"Unknown module: {module}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "module": module, "message": f"Module test failed: {e}"}


def build_report_document(doc: Optional[Dict[str, Any]], evaluation: Dict[str, Any],
                          models_status: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble a printable, structured investigation report from the analysis document."""
    if not doc or doc.get("status") != "ok":
        return {"status": "empty", "message": "No analysis has been completed yet.",
                "generated_at": datetime.now().isoformat()}

    forecast = doc.get("forecast", {}) or {}
    current = forecast.get("current", {}) or {}
    future = forecast.get("future", []) or []
    counterfactual = doc.get("counterfactual", {}) or {}
    ensemble = doc.get("ensemble", {}) or {}
    consensus = ensemble.get("consensus", {}) or {}

    return {
        "status": "ok",
        "generated_at": datetime.now().isoformat(),
        "source": doc.get("source"),
        "occurrence": doc.get("occurrence"),
        "filename": doc.get("filename"),
        "member": doc.get("member"),
        "file": {
            "filename": doc.get("filename"),
            "source": doc.get("source"),
            "member": doc.get("member"),
            "started_at": doc.get("started_at"),
            "finished_at": doc.get("finished_at"),
        },
        "traffic_summary": doc.get("traffic_summary", {}),
        "threat": {
            "threat_level": consensus.get("threat_level", "BENIGN"),
            "threat_status": consensus.get("threat_status", "NORMAL TRAFFIC"),
            "consensus_score": consensus.get("score", 0),
            "agreement_pct": consensus.get("agreement_pct", 0),
            "agreement_count": consensus.get("agreement_count", 0),
            "total_detectors": consensus.get("total_detectors", 8),
            "current_risk": current.get("risk", 0),
            "forecast_risk": float(future[-1].get("risk", 0)) if future else 0.0,
            "current_stage": current.get("stage", "Benign"),
            "predicted_stage": future[-1].get("stage", "") if future else "",
            "confidence": current.get("confidence", 0),
            "summary": consensus.get("summary", ""),
        },
        "forecast": {
            "current": current,
            "future": future,
            "steps": len(future),
        },
        "mitre_trajectory": doc.get("mitre_trajectory", []),
        "attack_graph": doc.get("graph", {}),
        "counterfactual": counterfactual,
        "detectors": ensemble.get("detectors", []),
        "recommendation": {
            "ensemble": consensus.get("recommendation", {}),
            "counterfactual": counterfactual.get("recommendation", {}),
        },
        "evaluation": evaluation,
        "models_status": models_status,
        "explanation": {
            "current": current.get("explanation", {}),
            "temporal": forecast.get("temporal_explanation", {}),
        },
    }
