"""TShark health detection and version probing.

This module is a thin compatibility layer over the single source of truth in
``netwatch.live.tshark_locator``. All discovery, resolution and version
probing logic lives in the locator; this module only re-exports the legacy
API used by the dashboard and existing tests.

For new code, import directly from ``netwatch.live.tshark_locator``.
"""

from __future__ import annotations

from netwatch.live.tshark_locator import (  # noqa: F401  (re-exported legacy API)
    detect_tshark,
    find_tshark,
    health_check,
    resolve_tshark,
)

__all__ = ["detect_tshark", "find_tshark", "health_check", "resolve_tshark"]