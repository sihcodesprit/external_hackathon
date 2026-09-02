"""
netwatch — Counterfactual Cyber World Model
===========================================

An AI-based Counterfactual Cyber World Model for multi-step network attack
forecasting and proactive cyber-defence decision support.

Problem Statement (SIH-26153): "AI based Network Attack Forecasting from
Network Traffic Data".

This package implements:
  * NetworkState representation (flow + packet + temporal features)
  * Temporal sequence dataset construction
  * LSTM-based World Model learning P(S_{t+1} | S_t)
  * K-step forward rollout / attack forecasting
  * MITRE ATT&CK attack-stage prediction
  * Predictive attack graph construction
  * Counterfactual defensive simulation + recommendation
  * SHAP-based explainability
  * Baseline + unseen-attack evaluation
  * Flask dashboard

No external (network / cloud) inference is required — everything runs offline
and all trained models are stored locally.
"""

__version__ = "2.0.0"
__title__ = "NetWatch - Counterfactual Cyber World Model"
