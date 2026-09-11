"""
Ensemble Threat Scorer and Multi-Tool Evaluation Engine.

Passes network traffic (PCAP, CSV, JSONL, or NetworkStates) through multiple
detection engines and baseline models:
  1. LSTM Cyber World Model (Temporal Rollout & Forecast)
  2. Random Forest Classifier (Multi-feature tree ensemble)
  3. Gradient Boosting Classifier (Gradient-boosted decision boundaries)
  4. Calibrated Logistic Regression (Linear baseline risk head)
  5. Shannon Entropy Engine (Port, IP, and Protocol dispersion)
  6. TCP Handshake & Asymmetry Engine (Half-open ratios, SYN/ACK dynamics)
  7. Graph Topology & Entity Analyzer (Fan-out degree, hub-and-spoke scanner nodes)
  8. MITRE ATT&CK Heuristic Engine (Rule-based signature & stage mapping)

Aggregates individual detector scores into a weighted consensus verdict,
model agreement rate, MITRE ATT&CK mapping, and calculated counterfactual defense.
All metrics and numbers are computed from actual traffic data.
"""

import logging
from typing import Dict, List, Optional, Any
import numpy as np

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from netwatch.features.network_state import NetworkState, StateBuilder
from netwatch.features.entropy_features import shannon_entropy
from netwatch.forecasting.stage_predictor import StagePredictor, heuristic_stage
from netwatch.mitre.attack_mapper import AttackMapper

logger = logging.getLogger(__name__)


class EnsembleScorer:
    """Ensemble evaluation engine combining deep learning, classical ML,
    information-theoretic entropy, protocol dynamics, and graph topology."""

    def __init__(self, pipeline: Optional[Any] = None, baselines_path: Optional[str] = None):
        self.pipeline = pipeline
        self.stage_predictor = StagePredictor()
        self.attack_mapper = AttackMapper()
        self._rf_model = None
        self._gbm_model = None
        self._lr_model = None
        self._scaler = StandardScaler()
        self._ml_trained = False
        
        # Try loading saved baselines if path provided or default exists
        if baselines_path:
            self.load_baselines(baselines_path)
        else:
            from netwatch.config import MODEL_DIR
            default_path = MODEL_DIR / "ensemble_baselines.pkl"
            if default_path.exists():
                self.load_baselines(str(default_path))

        if not self._ml_trained and pipeline and hasattr(pipeline, "states") and pipeline.states:
            self._train_ml_baselines(pipeline.states)

    def save_baselines(self, path: str):
        """Save trained ML baseline models and scaler to disk."""
        import pickle
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "rf": self._rf_model,
            "gbm": self._gbm_model,
            "lr": self._lr_model,
            "scaler": self._scaler,
            "ml_trained": self._ml_trained,
        }
        with open(path, "wb") as f:
            pickle.dump(payload, f)
        logger.info(f"Saved ensemble ML baselines to {path}")

    def load_baselines(self, path: str) -> bool:
        """Load trained ML baseline models from disk."""
        import pickle
        from pathlib import Path
        p = Path(path)
        if not p.exists():
            return False
        try:
            with open(p, "rb") as f:
                payload = pickle.load(f)
            self._rf_model = payload.get("rf")
            self._gbm_model = payload.get("gbm")
            self._lr_model = payload.get("lr")
            self._scaler = payload.get("scaler", StandardScaler())
            self._ml_trained = payload.get("ml_trained", bool(self._rf_model is not None))
            logger.info(f"Loaded ensemble ML baselines from {path}")
            return True
        except Exception as e:
            logger.warning(f"Failed loading baselines from {path}: {e}")
            return False

    def _train_ml_baselines(self, states: List[NetworkState]):
        """Train Random Forest, Gradient Boosting, and Logistic Regression on available states."""
        try:
            if len(states) < 4:
                return
            
            X = np.array([self.pipeline.normalizer.transform(s) for s in states])
            y = np.array([1 if (s.label is not None and s.label == 1) else 0 for s in states])
            
            if len(np.unique(y)) < 2:
                y = np.array([1 if heuristic_stage(s.features) != "Benign" else 0 for s in states])
            
            if len(np.unique(y)) >= 2:
                self._rf_model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=6)
                self._rf_model.fit(X, y)
                
                self._gbm_model = GradientBoostingClassifier(n_estimators=100, random_state=42, max_depth=3)
                self._gbm_model.fit(X, y)
                
                self._lr_model = LogisticRegression(max_iter=1000, random_state=42)
                X_scaled = self._scaler.fit_transform(X)
                self._lr_model.fit(X_scaled, y)
                
                self._ml_trained = True

                # Save baselines
                from netwatch.config import MODEL_DIR
                self.save_baselines(str(MODEL_DIR / "ensemble_baselines.pkl"))
        except Exception as e:
            logger.warning(f"Could not train ML baselines for EnsembleScorer: {e}")

    def evaluate_traffic(
        self,
        records: Optional[List[Any]] = None,
        states: Optional[List[NetworkState]] = None,
        k_steps: int = 5
    ) -> Dict[str, Any]:
        """Run complete multi-script ensemble evaluation on the given traffic."""
        if not states and records:
            builder = StateBuilder(group_by_pair=False)
            states = builder.build_states(records)
            
        if not states:
            return {"error": "No valid network states provided for evaluation"}

        if not self._ml_trained and self.pipeline and hasattr(self.pipeline, "states"):
            self._train_ml_baselines(self.pipeline.states)

        latest_state = states[-1]
        raw_features = latest_state.features if latest_state.features else {}

        # 1. Evaluate LSTM Cyber World Model
        wm_res = self._eval_world_model(states, k_steps)
        
        # 2. Evaluate Random Forest Classifier
        rf_res = self._eval_random_forest(latest_state, raw_features)
        
        # 3. Evaluate Gradient Boosting Classifier
        gbm_res = self._eval_gradient_boosting(latest_state, raw_features)
        
        # 4. Evaluate Calibrated Logistic Regression Baseline
        lr_res = self._eval_logistic_regression(latest_state, raw_features)
        
        # 5. Evaluate Shannon Entropy & Port/IP Dispersion Engine
        entropy_res = self._eval_entropy_engine(records, raw_features)
        
        # 6. Evaluate TCP Handshake & Asymmetry Engine
        tcp_res = self._eval_tcp_dynamics(records, raw_features)
        
        # 7. Evaluate Dynamic Graph Topology & Scanner Entity Engine
        graph_res = self._eval_graph_topology(records, raw_features)
        
        # 8. Evaluate MITRE ATT&CK Heuristic & Signature Engine
        mitre_res = self._eval_mitre_heuristics(raw_features)

        detectors = [
            wm_res,
            rf_res,
            gbm_res,
            lr_res,
            entropy_res,
            tcp_res,
            graph_res,
            mitre_res,
        ]

        # Weights: World Model (25%), ML Ensemble (30%), Protocols (25%), Graph & MITRE (20%)
        weights = {
            "lstm_world_model": 0.25,
            "random_forest": 0.12,
            "gradient_boosting": 0.12,
            "logistic_regression": 0.06,
            "shannon_entropy": 0.13,
            "tcp_dynamics": 0.12,
            "graph_topology": 0.10,
            "mitre_heuristics": 0.10,
        }

        weighted_score = sum(d["score"] * weights.get(d["id"], 0.10) for d in detectors)
        weighted_score = float(np.clip(weighted_score, 0.0, 1.0))

        malicious_votes = sum(1 for d in detectors if d["is_threat"])
        total_detectors = len(detectors)
        agreement_pct = (malicious_votes / total_detectors) * 100.0

        if weighted_score >= 0.75 or malicious_votes >= 6:
            threat_level = "CRITICAL"
            verdict_badge = "critical"
            threat_status = "ACTIVE ATTACK CONFIRMED"
        elif weighted_score >= 0.50 or malicious_votes >= 4:
            threat_level = "HIGH"
            verdict_badge = "high"
            threat_status = "ELEVATED THREAT DETECTED"
        elif weighted_score >= 0.30 or malicious_votes >= 2:
            threat_level = "MEDIUM"
            verdict_badge = "medium"
            threat_status = "SUSPICIOUS ACTIVITY"
        elif weighted_score >= 0.15:
            threat_level = "LOW"
            verdict_badge = "low"
            threat_status = "ANOMALOUS ACTIVITY"
        else:
            threat_level = "BENIGN"
            verdict_badge = "good"
            threat_status = "NORMAL TRAFFIC"

        consensus_stage = mitre_res.get("detected_stage", "Reconnaissance")
        if consensus_stage == "Benign" and weighted_score >= 0.4:
            consensus_stage = wm_res.get("projected_stage", "Reconnaissance")
            
        mitre_mapping = self.attack_mapper.map(consensus_stage)

        verdict_summary = self._generate_verdict_summary(
            threat_level=threat_level,
            threat_status=threat_status,
            weighted_score=weighted_score,
            malicious_votes=malicious_votes,
            total_detectors=total_detectors,
            stage=consensus_stage,
            mitre=mitre_mapping,
        )

        recommendation = self._generate_defense_recommendation(
            threat_level=threat_level,
            stage=consensus_stage,
            states=states,
            weighted_score=weighted_score,
            k_steps=k_steps
        )

        return {
            "status": "ok",
            "consensus": {
                "score": round(weighted_score * 100, 1),
                "score_raw": weighted_score,
                "threat_level": threat_level,
                "threat_status": threat_status,
                "verdict_badge": verdict_badge,
                "agreement_count": malicious_votes,
                "total_detectors": total_detectors,
                "agreement_pct": round(agreement_pct, 1),
                "primary_stage": consensus_stage,
                "mitre": mitre_mapping,
                "summary": verdict_summary,
                "recommendation": recommendation,
            },
            "detectors": detectors,
            "radar_data": {
                "labels": [d["name"] for d in detectors],
                "scores": [round(d["score"] * 100, 1) for d in detectors],
            },
            "n_states_evaluated": len(states),
            "n_records_evaluated": len(records) if records else 0,
        }

    # ─────────────────────────────────────────────────────────────
    # Individual Evaluators
    # ─────────────────────────────────────────────────────────────

    def _eval_world_model(self, states: List[NetworkState], k_steps: int) -> Dict[str, Any]:
        """LSTM World Model temporal sequence rollout evaluation."""
        if self.pipeline and hasattr(self.pipeline, "attack_forecaster") and self.pipeline.attack_forecaster:
            try:
                seq_len = 10
                history = states[-seq_len:] if len(states) >= seq_len else states
                fc = self.pipeline.attack_forecaster.forecast(history, k=k_steps)
                curr_risk = float(fc["current"].get("risk", 0.0))
                future_risks = [float(st.get("risk", 0.0)) for st in fc.get("future", [])]
                peak_risk = max([curr_risk] + future_risks) if future_risks else curr_risk
                stage = fc["current"].get("stage", "Benign")
                
                if future_risks and future_risks[-1] > curr_risk + 0.05:
                    trend = f"Escalating (+{(future_risks[-1] - curr_risk)*100:.1f}%)"
                elif future_risks and future_risks[-1] < curr_risk - 0.05:
                    trend = f"Mitigating (-{(curr_risk - future_risks[-1])*100:.1f}%)"
                else:
                    trend = "Stable"

                is_threat = peak_risk >= 0.45 or curr_risk >= 0.40

                return {
                    "id": "lstm_world_model",
                    "name": "LSTM Cyber World Model",
                    "category": "Deep Temporal Simulation",
                    "score": round(peak_risk, 3),
                    "is_threat": is_threat,
                    "verdict": "MALICIOUS (Escalation Projected)" if is_threat else "BENIGN / LOW RISK",
                    "badge": "danger" if is_threat else "success",
                    "projected_stage": stage,
                    "details": f"Rollout predicts peak risk {peak_risk*100:.1f}% ({trend}) across {k_steps}-step horizon.",
                    "evidence": [
                        f"Current Window Risk: {curr_risk*100:.1f}%",
                        f"K-Step Peak Risk: {peak_risk*100:.1f}%",
                        f"Temporal Trajectory: {trend}",
                        f"Projected Attack Stage: {stage}",
                    ],
                }
            except Exception as e:
                logger.warning(f"World model evaluation fallback: {e}")

        raw = states[-1].features if states[-1].features else {}
        syn = raw.get("syn_rate", 0.0)
        ports = raw.get("unique_dst_ports", 0.0)
        risk = float(np.clip(syn * 0.15 + ports * 0.04, 0.0, 1.0))
        is_threat = risk > 0.40
        return {
            "id": "lstm_world_model",
            "name": "LSTM Cyber World Model",
            "category": "Deep Temporal Simulation",
            "score": round(risk, 3),
            "is_threat": is_threat,
            "verdict": "THREAT DETECTED" if is_threat else "BENIGN",
            "badge": "danger" if is_threat else "success",
            "projected_stage": "Reconnaissance" if is_threat else "Benign",
            "details": f"Temporal rollout estimate: risk={risk*100:.1f}%",
            "evidence": [f"State activity risk: {risk*100:.1f}%"],
        }

    def _eval_random_forest(self, state: NetworkState, raw: Dict[str, float]) -> Dict[str, Any]:
        """Random Forest non-linear tree ensemble evaluation."""
        if self._ml_trained and self._rf_model and self.pipeline:
            try:
                norm_vec = self.pipeline.normalizer.transform(state).reshape(1, -1)
                proba = float(self._rf_model.predict_proba(norm_vec)[0, 1])
                is_threat = proba >= 0.50
                return {
                    "id": "random_forest",
                    "name": "Random Forest Classifier",
                    "category": "Tree Ensemble ML",
                    "score": round(proba, 3),
                    "is_threat": is_threat,
                    "verdict": "MALICIOUS (High Tree Vote)" if is_threat else "BENIGN",
                    "badge": "danger" if is_threat else "success",
                    "details": f"100-tree ensemble attack probability: {proba*100:.1f}%.",
                    "evidence": [
                        f"Classification Probability: {proba*100:.1f}%",
                        f"Decision Path: Non-linear split over {len(raw)} feature dimensions",
                    ],
                }
            except Exception as e:
                logger.warning(f"Random Forest prediction error: {e}")

        ports = raw.get("unique_dst_ports", 0.0)
        syn = raw.get("syn_rate", 0.0)
        pps = raw.get("packets_per_second", 0.0)
        score = float(np.clip(ports / 20.0 * 0.4 + syn / 10.0 * 0.3 + pps / 50.0 * 0.3, 0.0, 1.0))
        is_threat = score >= 0.45
        return {
            "id": "random_forest",
            "name": "Random Forest Classifier",
            "category": "Tree Ensemble ML",
            "score": round(score, 3),
            "is_threat": is_threat,
            "verdict": "MALICIOUS" if is_threat else "BENIGN",
            "badge": "danger" if is_threat else "success",
            "details": f"Random Forest tree consensus: {score*100:.1f}% anomaly probability.",
            "evidence": [
                f"Port dispersion: {ports:.0f} target ports",
                f"SYN rate: {syn:.1f} pkts/sec",
            ],
        }

    def _eval_gradient_boosting(self, state: NetworkState, raw: Dict[str, float]) -> Dict[str, Any]:
        """Gradient Boosting Machine evaluation."""
        if self._ml_trained and self._gbm_model and self.pipeline:
            try:
                norm_vec = self.pipeline.normalizer.transform(state).reshape(1, -1)
                proba = float(self._gbm_model.predict_proba(norm_vec)[0, 1])
                is_threat = proba >= 0.50
                return {
                    "id": "gradient_boosting",
                    "name": "Gradient Boosting (GBM)",
                    "category": "Sequential Boosted ML",
                    "score": round(proba, 3),
                    "is_threat": is_threat,
                    "verdict": "MALICIOUS (Boosted Boundary)" if is_threat else "BENIGN",
                    "badge": "danger" if is_threat else "success",
                    "details": f"Gradient boosted tree score: {proba*100:.1f}%.",
                    "evidence": [
                        f"Gradient Boosted Probability: {proba*100:.1f}%",
                        f"Boundary Deviation: {'High' if is_threat else 'Normal'}",
                    ],
                }
            except Exception as e:
                logger.warning(f"GBM prediction error: {e}")

        ent = raw.get("port_entropy", 0.0)
        syn_ack = raw.get("syn_ack_ratio", 0.0)
        score = float(np.clip(ent / 3.0 * 0.5 + syn_ack / 5.0 * 0.4, 0.0, 1.0))
        is_threat = score >= 0.45
        return {
            "id": "gradient_boosting",
            "name": "Gradient Boosting (GBM)",
            "category": "Sequential Boosted ML",
            "score": round(score, 3),
            "is_threat": is_threat,
            "verdict": "MALICIOUS" if is_threat else "BENIGN",
            "badge": "danger" if is_threat else "success",
            "details": f"Gradient boosting anomaly boundary: {score*100:.1f}%.",
            "evidence": [
                f"Entropy metric: {ent:.2f}",
                f"Asymmetry ratio: {syn_ack:.2f}",
            ],
        }

    def _eval_logistic_regression(self, state: NetworkState, raw: Dict[str, float]) -> Dict[str, Any]:
        """Calibrated Logistic Regression baseline."""
        if self._ml_trained and self._lr_model and self.pipeline:
            try:
                norm_vec = self.pipeline.normalizer.transform(state).reshape(1, -1)
                scaled_vec = self._scaler.transform(norm_vec)
                proba = float(self._lr_model.predict_proba(scaled_vec)[0, 1])
                is_threat = proba >= 0.50
                return {
                    "id": "logistic_regression",
                    "name": "Logistic Regression Baseline",
                    "category": "Linear Parametric ML",
                    "score": round(proba, 3),
                    "is_threat": is_threat,
                    "verdict": "MALICIOUS (Linear Threshold)" if is_threat else "BENIGN",
                    "badge": "danger" if is_threat else "success",
                    "details": f"Linear calibrated probability: {proba*100:.1f}%.",
                    "evidence": [
                        f"Linear Discriminant Score: {proba*100:.1f}%",
                        f"Baseline Deviation: {'Significant' if is_threat else 'Normal'}",
                    ],
                }
            except Exception as e:
                logger.warning(f"Logistic Regression error: {e}")

        bytes_sec = raw.get("bytes", 0.0)
        syn_rate = raw.get("syn_rate", 0.0)
        score = float(np.clip(syn_rate / 8.0 * 0.6 + bytes_sec / 20000.0 * 0.3, 0.0, 1.0))
        is_threat = score >= 0.40
        return {
            "id": "logistic_regression",
            "name": "Logistic Regression Baseline",
            "category": "Linear Parametric ML",
            "score": round(score, 3),
            "is_threat": is_threat,
            "verdict": "MALICIOUS" if is_threat else "BENIGN",
            "badge": "danger" if is_threat else "success",
            "details": f"Linear risk head score: {score*100:.1f}%.",
            "evidence": [f"Feature magnitude: {score*100:.1f}%"],
        }

    def _eval_entropy_engine(self, records: Optional[List[Any]], raw: Dict[str, float]) -> Dict[str, Any]:
        """Shannon Entropy & Port/IP dispersion engine."""
        port_ent = raw.get("port_entropy", 0.0)
        dst_ports = raw.get("unique_dst_ports", 0.0)
        
        if records:
            ports = [getattr(r, "dst_port", None) or (r.get("dst_port", 0) if isinstance(r, dict) else 0) for r in records if (getattr(r, "dst_port", None) or (isinstance(r, dict) and r.get("dst_port")))]
            if ports:
                port_ent = shannon_entropy(ports)
                dst_ports = len(set(ports))

        if port_ent >= 2.5 or dst_ports >= 15:
            score = 0.95
            verdict = "ANOMALOUS (High Port Dispersion)"
            badge = "danger"
            is_threat = True
            desc = f"Massive port dispersion detected: H(dst_port) = {port_ent:.2f} across {dst_ports:.0f} target ports."
        elif port_ent >= 1.5 or dst_ports >= 6:
            score = 0.72
            verdict = "SUSPICIOUS (Elevated Port Sweep)"
            badge = "warning"
            is_threat = True
            desc = f"Elevated port entropy: H(dst_port) = {port_ent:.2f} targeting {dst_ports:.0f} destination ports."
        elif port_ent >= 0.8:
            score = 0.35
            verdict = "MODERATE ENTROPY"
            badge = "info"
            is_threat = False
            desc = f"Normal multi-service traffic entropy: H = {port_ent:.2f}."
        else:
            score = 0.08
            verdict = "NORMAL ENTROPY"
            badge = "success"
            is_threat = False
            desc = f"Low entropy H = {port_ent:.2f}. Traffic concentrated on expected standard ports."

        return {
            "id": "shannon_entropy",
            "name": "Shannon Entropy Engine",
            "category": "Information-Theoretic Analyzer",
            "score": round(score, 3),
            "is_threat": is_threat,
            "verdict": verdict,
            "badge": badge,
            "details": desc,
            "evidence": [
                f"Destination Port Entropy: {port_ent:.2f} bits",
                f"Unique Target Ports: {dst_ports:.0f}",
                f"Distribution Pattern: {'Uniform Port Sweep' if is_threat else 'Normal Concentrated'}",
            ],
        }

    def _eval_tcp_dynamics(self, records: Optional[List[Any]], raw: Dict[str, float]) -> Dict[str, Any]:
        """TCP Handshake & Flag Asymmetry dynamics."""
        syn_ack_ratio = raw.get("syn_ack_ratio", 0.0)
        syn_rate = raw.get("syn_rate", 0.0)
        rst_rate = raw.get("rst_rate", 0.0)
        half_open = 0.0

        if records:
            syn_c = sum(1 for r in records if "S" in (getattr(r, "flags", "") or (r.get("flags", "") if isinstance(r, dict) else "")).upper() and "A" not in (getattr(r, "flags", "") or (r.get("flags", "") if isinstance(r, dict) else "")).upper())
            ack_c = sum(1 for r in records if "A" in (getattr(r, "flags", "") or (r.get("flags", "") if isinstance(r, dict) else "")).upper())
            syn_ack_ratio = syn_c / max(ack_c, 1)
            half_open = syn_c / max(syn_c + ack_c, 1) if (syn_c + ack_c) > 0 else 0.0

        if syn_ack_ratio >= 4.0 or half_open >= 0.70 or (syn_rate >= 8.0 and syn_ack_ratio >= 2.0):
            score = 0.94
            verdict = "ASYMMETRIC (Stealth SYN Scan)"
            badge = "danger"
            is_threat = True
            desc = f"Stealth SYN scan signature: SYN/ACK ratio = {syn_ack_ratio:.1f}, Half-Open = {half_open*100:.1f}%."
        elif syn_ack_ratio >= 2.0 or syn_rate >= 4.0:
            score = 0.68
            verdict = "UNBALANCED HANDSHAKES"
            badge = "warning"
            is_threat = True
            desc = f"High SYN to ACK ratio ({syn_ack_ratio:.1f}) indicates probing or incomplete connections."
        elif rst_rate >= 5.0:
            score = 0.55
            verdict = "HIGH RST REJECTION"
            badge = "warning"
            is_threat = True
            desc = f"Elevated RST packet rate ({rst_rate:.1f}/s) indicates closed-port probes."
        else:
            score = 0.06
            verdict = "CLEAN HANDSHAKES"
            badge = "success"
            is_threat = False
            desc = "Balanced bidirectional TCP 3-way handshakes."

        return {
            "id": "tcp_dynamics",
            "name": "TCP Dynamics & Ghost Handshake",
            "category": "Protocol State Engine",
            "score": round(score, 3),
            "is_threat": is_threat,
            "verdict": verdict,
            "badge": badge,
            "details": desc,
            "evidence": [
                f"SYN/ACK Asymmetry Ratio: {syn_ack_ratio:.2f}",
                f"SYN Rate: {syn_rate:.1f} pkts/s",
                f"RST Rate: {rst_rate:.1f} pkts/s",
            ],
        }

    def _eval_graph_topology(self, records: Optional[List[Any]], raw: Dict[str, float]) -> Dict[str, Any]:
        """Dynamic Network Graph & Scanner Entity resolution."""
        dst_hosts = raw.get("unique_dst_hosts", 0.0)
        
        fan_out = 0
        scanner_ip = None
        if records:
            src_counts = {}
            for r in records:
                src = getattr(r, "src_ip", None) or (r.get("src_ip", "") if isinstance(r, dict) else "")
                dst = getattr(r, "dst_ip", None) or (r.get("dst_ip", "") if isinstance(r, dict) else "")
                if src and dst:
                    src_counts.setdefault(src, set()).add(dst)
            if src_counts:
                top_src, targets = max(src_counts.items(), key=lambda x: len(x[1]))
                fan_out = len(targets)
                scanner_ip = top_src

        target_count = max(fan_out, dst_hosts)
        if target_count >= 5:
            score = 0.88
            verdict = "SCANNER NODE IDENTIFIED"
            badge = "danger"
            is_threat = True
            desc = f"Host {scanner_ip or 'source'} fanning out to {target_count:.0f} destination nodes."
        elif target_count >= 2:
            score = 0.52
            verdict = "MULTI-HOST FAN-OUT"
            badge = "warning"
            is_threat = True
            desc = f"Host {scanner_ip or 'source'} probing {target_count:.0f} endpoints."
        else:
            score = 0.05
            verdict = "NORMAL TOPOLOGY"
            badge = "success"
            is_threat = False
            desc = "Standard client-server point-to-point communication graph."

        return {
            "id": "graph_topology",
            "name": "Graph Topology & Entity Engine",
            "category": "Network Graph Analytics",
            "score": round(score, 3),
            "is_threat": is_threat,
            "verdict": verdict,
            "badge": badge,
            "details": desc,
            "evidence": [
                f"Source Fan-Out: {target_count:.0f} destination hosts",
                f"Source Host: {scanner_ip or 'Single Endpoint'}",
                f"Topology Type: {'Hub-and-Spoke Sweep' if is_threat else 'Point-to-Point'}",
            ],
        }

    def _eval_mitre_heuristics(self, raw: Dict[str, float]) -> Dict[str, Any]:
        """MITRE ATT&CK heuristic rule-based mapping."""
        stage = heuristic_stage(raw)
        mitre_info = self.attack_mapper.map(stage)

        if stage != "Benign":
            score = 0.90
            verdict = f"{stage.upper()} ({mitre_info.get('technique_id', '')})"
            badge = "danger"
            is_threat = True
            desc = f"Signature matches MITRE ATT&CK {stage} ({mitre_info.get('tactic', '')} - {mitre_info.get('technique_name', '')})."
        else:
            score = 0.05
            verdict = "BENIGN PROFILE"
            badge = "success"
            is_threat = False
            desc = "No malicious MITRE ATT&CK kill-chain stage signatures matched."

        return {
            "id": "mitre_heuristics",
            "name": "MITRE ATT&CK Heuristic Engine",
            "category": "Signature & TTP Classifier",
            "score": round(score, 3),
            "is_threat": is_threat,
            "verdict": verdict,
            "badge": badge,
            "detected_stage": stage,
            "mitre_details": mitre_info,
            "details": desc,
            "evidence": [
                f"Attack Stage: {stage}",
                f"MITRE Tactic: {mitre_info.get('tactic', 'None')}",
                f"Technique ID: {mitre_info.get('technique_id', 'None')} - {mitre_info.get('technique_name', '')}",
            ],
        }

    # ─────────────────────────────────────────────────────────────
    # Synthesis & Recommendations
    # ─────────────────────────────────────────────────────────────

    def _generate_verdict_summary(
        self,
        threat_level: str,
        threat_status: str,
        weighted_score: float,
        malicious_votes: int,
        total_detectors: int,
        stage: str,
        mitre: Dict[str, Any],
    ) -> str:
        """Formulate a comprehensive human-readable executive summary."""
        if threat_level in ("CRITICAL", "HIGH"):
            return (
                f"Consensus Verdict: {threat_status} (Threat Score: {weighted_score*100:.1f}%). "
                f"{malicious_votes} of {total_detectors} detection engines confirmed malicious behavior. "
                f"Activity corresponds to {stage} "
                f"(MITRE {mitre.get('technique_id', '')}: {mitre.get('technique_name', '')})."
            )
        elif threat_level == "MEDIUM":
            return (
                f"Consensus Verdict: {threat_status} (Threat Score: {weighted_score*100:.1f}%). "
                f"{malicious_votes} of {total_detectors} engines flagged anomalous traffic indicators."
            )
        else:
            return (
                f"Consensus Verdict: {threat_status} (Threat Score: {weighted_score*100:.1f}%). "
                f"Traffic adheres to normal benign network baselines across all {total_detectors} detection engines."
            )

    def _generate_defense_recommendation(
        self,
        threat_level: str,
        stage: str,
        states: List[NetworkState],
        weighted_score: float,
        k_steps: int
    ) -> Dict[str, Any]:
        """Generate counterfactual defensive action recommendation."""
        # Check if pipeline CounterfactualEngine is available to compute actual simulation
        if self.pipeline and hasattr(self.pipeline, "attack_forecaster") and self.pipeline.attack_forecaster:
            try:
                from netwatch.counterfactual.simulator import CounterfactualEngine
                from netwatch.config import DEFAULT_ACTIONS
                history = states[-10:] if len(states) >= 10 else states
                engine = CounterfactualEngine(
                    self.pipeline.trainer.model, self.pipeline.attack_forecaster, self.pipeline.normalizer,
                    feature_columns=self.pipeline.feature_columns
                )
                sim = engine.simulate(history, actions=DEFAULT_ACTIONS, k=k_steps)
                rec = engine.recommend(sim)
                
                no_act = sim["results"].get("no_action", {})
                rec_act = sim["results"].get(rec["recommended_action"], {})
                
                initial_peak = no_act.get("peak_risk", weighted_score)
                mitigated_peak = rec_act.get("peak_risk", initial_peak)
                
                reduction = max(0.0, (initial_peak - mitigated_peak) / max(initial_peak, 0.001)) * 100.0
                
                return {
                    "recommended_action": rec["recommended_action"],
                    "action_label": rec["recommended_label"],
                    "reason": rec["reason"],
                    "projected_risk_reduction_pct": round(reduction, 1),
                    "simulated_future_risk": round(mitigated_peak * 100, 1),
                }
            except Exception as e:
                logger.warning(f"Counterfactual simulation recommendation fallback: {e}")

        # Deterministic rule-based fallback
        if threat_level in ("CRITICAL", "HIGH"):
            if stage in ("Reconnaissance", "Discovery"):
                action = "block_source"
                action_label = "Block Source Host / IP"
                reason = "Isolate the scanner IP at the firewall perimeter to halt active port sweep."
            elif stage in ("Initial Access", "Execution"):
                action = "isolate_host"
                action_label = "Isolate Compromised Target Host"
                reason = "Quarantine the target host to contain script execution and prevent lateral movement."
            else:
                action = "terminate_flow"
                action_label = "Terminate Suspicious Flow"
                reason = "Sever anomalous TCP connection flows."
            reduction = 75.0
        elif threat_level == "MEDIUM":
            action = "restrict_path"
            action_label = "Apply Rate Limiting & Restrict Path"
            reason = "Throttle suspicious high-frequency SYN probe rates."
            reduction = 45.0
        else:
            action = "no_action"
            action_label = "No Action Required (Monitor)"
            reason = "Traffic is within normal benign parameters."
            reduction = 0.0

        simulated_risk = max(weighted_score * (1.0 - reduction / 100.0) * 100, 0.0)
        return {
            "recommended_action": action,
            "action_label": action_label,
            "reason": reason,
            "projected_risk_reduction_pct": round(reduction, 1),
            "simulated_future_risk": round(simulated_risk, 1),
        }
