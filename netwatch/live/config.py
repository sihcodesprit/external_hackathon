"""Live monitoring configuration. All values from env vars or config.yaml live section."""

import os
from typing import List, Optional


def _env(key: str, default):
    """Read env var with type coercion."""
    v = os.getenv(key)
    if v is None:
        return default
    if isinstance(default, bool):
        return v.lower() in ("1", "true", "yes")
    if isinstance(default, int):
        return int(v)
    if isinstance(default, float):
        return float(v)
    if isinstance(default, list):
        return [x.strip() for x in v.split(",")]
    return v


LIVE_ENABLED: bool = _env("NETWATCH_LIVE_ENABLED", True)

# TShark executable. Prefer the explicit TSHARK_PATH override; fall back to
# the legacy NETWATCH_TSHARK_PATH name. Empty = auto-discover (tshark_locator).
TSHARK_PATH: str = (_env("TSHARK_PATH", "") or _env("NETWATCH_TSHARK_PATH", "") or "")
TSHARK_OUTPUT_FORMAT: str = _env("NETWATCH_LIVE_TSHARK_FORMAT", "ek")
TSHARK_BPF_FILTER: str = _env("NETWATCH_LIVE_BPF_FILTER", "")
TSHARK_SNAPLEN: int = _env("NETWATCH_LIVE_SNAPLEN", 65535)
TSHARK_PROMISCUOUS: bool = _env("NETWATCH_LIVE_PROMISCUOUS", True)

LIVE_DEFAULT_INTERFACE: str = _env("NETWATCH_LIVE_DEFAULT_INTERFACE", "")
LIVE_WINDOW_SIZE: int = _env("NETWATCH_LIVE_WINDOW_SIZE", 30)
LIVE_STEP_SIZE: int = _env("NETWATCH_LIVE_STEP_SIZE", 5)
LIVE_FORECAST_HORIZON: int = _env("NETWATCH_LIVE_FORECAST_HORIZON", 5)
LIVE_MAX_EVENT_QUEUE: int = _env("NETWATCH_LIVE_MAX_EVENT_QUEUE", 10000)
LIVE_MAX_EVENTS_PER_WINDOW: int = _env("NETWATCH_LIVE_MAX_EVENTS_PER_WINDOW", 8000)
LIVE_DASHBOARD_UPDATE_INTERVAL: float = _env("NETWATCH_LIVE_DASHBOARD_UPDATE_INTERVAL", 1.0)
LIVE_MAX_HISTORY_SECONDS: int = _env("NETWATCH_LIVE_MAX_HISTORY_SECONDS", 600)
LIVE_MODEL_TYPE: str = _env("NETWATCH_LIVE_MODEL_TYPE", "linear")
LIVE_MIN_STATES_FOR_MODEL: int = _env("NETWATCH_LIVE_MIN_STATES_FOR_MODEL", 8)
LIVE_MODEL_REFIT_INTERVAL: int = _env("NETWATCH_LIVE_MODEL_REFIT_INTERVAL", 3)
LIVE_MAX_STATE_HISTORY: int = _env("NETWATCH_LIVE_MAX_STATE_HISTORY", 120)
LIVE_EVENTS_PER_SECOND_LOG: int = _env("NETWATCH_LIVE_EVENTS_PER_SECOND_LOG", 1000)
LIVE_TEST_TIMEOUT: int = _env("NETWATCH_LIVE_TEST_TIMEOUT", 30)

# ── URL Monitor (destination-observed live capture) ─────────────
LIVE_URL_DNS_REFRESH_SECONDS: int = _env("NETWATCH_LIVE_URL_DNS_REFRESH_SECONDS", 60)
LIVE_URL_ALLOW_PRIVATE_HOSTS: bool = _env("NETWATCH_LIVE_URL_ALLOW_PRIVATE_HOSTS", False)
