"""Sliding window manager for live packet aggregation."""

import logging
import time
from collections import deque
from typing import List, Optional

from netwatch.live.config import LIVE_WINDOW_SIZE, LIVE_STEP_SIZE, LIVE_MAX_EVENTS_PER_WINDOW

logger = logging.getLogger(__name__)


class WindowManager:
    """Manages sliding time windows for live packet aggregation.

    Collects events and yields completed window batches every STEP_SIZE seconds,
    each covering WINDOW_SIZE seconds of events.
    """

    def __init__(self, window_size: int = LIVE_WINDOW_SIZE,
                 step_size: int = LIVE_STEP_SIZE):
        self.window_size = window_size
        self.step_size = step_size
        self._events: deque = deque(maxlen=LIVE_MAX_EVENTS_PER_WINDOW)
        self._window_start: Optional[float] = None
        self._last_step_time: Optional[float] = None
        self._total_events_received = 0
        self._total_events_processed = 0
        self._total_events_dropped = 0

    def add_event(self, event: dict):
        now = time.time()
        self._total_events_received += 1
        if len(self._events) >= self._events.maxlen:
            self._total_events_dropped += 1
            return
        self._events.append(event)
        if self._window_start is None:
            self._window_start = now
        if self._last_step_time is None:
            self._last_step_time = now

    def check_step(self) -> Optional[List[dict]]:
        """Check if a window step has elapsed. Returns events in the window if so."""
        now = time.time()
        if self._last_step_time is None:
            return None
        elapsed = now - self._last_step_time
        if elapsed < self.step_size:
            return None

        window_end = self._last_step_time + self.window_size
        window_events = [
            e for e in self._events
            if self._get_event_time(e) <= window_end
            and self._get_event_time(e) >= self._last_step_time
        ]

        if not window_events:
            window_events = [
                e for e in self._events
                if self._get_event_time(e) >= (now - self.window_size)
            ]

        self._last_step_time = now
        self._total_events_processed += len(window_events)
        return window_events

    def get_current_window_events(self) -> List[dict]:
        """Get events in the current (incomplete) window."""
        now = time.time()
        return [
            e for e in self._events
            if self._get_event_time(e) >= (now - self.window_size)
        ]

    @property
    def stats(self) -> dict:
        return {
            "events_received": self._total_events_received,
            "events_processed": self._total_events_processed,
            "events_dropped": self._total_events_dropped,
            "events_buffered": len(self._events),
        }

    @staticmethod
    def _get_event_time(event: dict) -> float:
        ts = event.get("timestamp", "")
        if isinstance(ts, (int, float)):
            return float(ts)
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return time.time()

    def reset(self):
        self._events.clear()
        self._window_start = None
        self._last_step_time = None
        self._total_events_received = 0
        self._total_events_processed = 0
        self._total_events_dropped = 0