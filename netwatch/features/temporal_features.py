"""
Temporal / Jitter Features.

Implements inter-arrival time statistics, coefficient of variation,
autocorrelation, periodicity score, burstiness, and optional FFT analysis.
"""

from typing import Dict, List, Optional

import numpy as np


def compute_temporal_features(records: List[Dict],
                               prev_iat_stats: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """
    Compute temporal/jitter features from a window of records.

    Args:
        records: List of packet/flow dicts with 'timestamp' field (ISO format)
        prev_iat_stats: Previous window's IAT statistics (for trajectory)

    Returns:
        Dict of temporal features
    """
    if not records:
        return _empty_temporal_features()

    # Parse timestamps and compute inter-arrival times
    timestamps = []
    for r in records:
        ts_str = r.get("timestamp", "")
        if ts_str:
            try:
                # Handle various timestamp formats
                ts = ts_str.replace("Z", "+00:00")
                timestamps.append(float(ts) if ts.replace(".", "").replace("-", "").isdigit()
                                else __import__("datetime").datetime.fromisoformat(ts).timestamp())
            except Exception:
                pass

    if len(timestamps) < 2:
        return _empty_temporal_features()

    timestamps.sort()
    iats = np.diff(timestamps)  # Inter-arrival times in seconds
    iats = iats[iats > 0]  # Remove zero/negative IATs

    if len(iats) == 0:
        return _empty_temporal_features()

    # Basic IAT statistics
    iat_mean = float(np.mean(iats))
    iat_std = float(np.std(iats))
    iat_variance = float(np.var(iats))
    iat_cv = iat_std / iat_mean if iat_mean > 0 else 0.0  # Coefficient of variation
    iat_min = float(np.min(iats))
    iat_max = float(np.max(iats))

    # Autocorrelation (lag-1)
    iat_autocorr = 0.0
    if len(iats) > 1:
        try:
            if np.std(iats[:-1]) > 0 and np.std(iats[1:]) > 0:
                iat_autocorr = float(np.corrcoef(iats[:-1], iats[1:])[0, 1])
                if np.isnan(iat_autocorr):
                    iat_autocorr = 0.0
            else:
                iat_autocorr = 0.0
        except Exception:
            iat_autocorr = 0.0

    # Periodicity score (based on autocorrelation peak)
    periodicity_score = max(0.0, iat_autocorr) if iat_autocorr > 0 else 0.0

    # Burstiness (using Kim & Kim burstiness parameter)
    # B = (σ - μ) / (σ + μ) for positive values, ranges [-1, 1]
    burstiness = 0.0
    if iat_mean + iat_std > 0:
        burstiness = (iat_std - iat_mean) / (iat_std + iat_mean)

    # Optional FFT analysis
    fft_dominant_freq = 0.0
    fft_spectral_power = 0.0
    if len(iats) >= 8:
        try:
            fft_vals = np.fft.fft(iats - np.mean(iats))
            freqs = np.fft.fftfreq(len(iats), d=iat_mean if iat_mean > 0 else 1.0)
            power = np.abs(fft_vals) ** 2
            # Only positive frequencies
            pos_mask = freqs > 0
            if np.any(pos_mask):
                pos_power = power[pos_mask]
                pos_freqs = freqs[pos_mask]
                total_power = float(np.sum(pos_power))
                if total_power > 0:
                    max_idx = np.argmax(pos_power)
                    fft_dominant_freq = float(pos_freqs[max_idx])
                    fft_spectral_power = float(pos_power[max_idx] / total_power)
        except Exception:
            pass

    features = {
        "iat_mean": iat_mean,
        "iat_std": iat_std,
        "iat_variance": iat_variance,
        "iat_cv": iat_cv,
        "iat_min": iat_min,
        "iat_max": iat_max,
        "iat_autocorr": iat_autocorr,
        "periodicity_score": periodicity_score,
        "burstiness": burstiness,
        "fft_dominant_freq": fft_dominant_freq,
        "fft_spectral_power": fft_spectral_power,
    }

    return features


def _empty_temporal_features() -> Dict[str, float]:
    return {
        "iat_mean": 0.0,
        "iat_std": 0.0,
        "iat_variance": 0.0,
        "iat_cv": 0.0,
        "iat_min": 0.0,
        "iat_max": 0.0,
        "iat_autocorr": 0.0,
        "periodicity_score": 0.0,
        "burstiness": 0.0,
        "fft_dominant_freq": 0.0,
        "fft_spectral_power": 0.0,
    }
