"""Simple in-memory rate limiting helpers."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimit:
    max_requests: int
    window_seconds: int


class InMemoryRateLimiter:
    """Token bucket limiter keyed by arbitrary strings."""

    def __init__(self, *, limit: RateLimit) -> None:
        self._limit = limit
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        timestamp = now if now is not None else time.monotonic()
        window_start = timestamp - self._limit.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] < window_start:
                events.popleft()

            if len(events) >= self._limit.max_requests:
                return False

            events.append(timestamp)
            return True


__all__ = ["InMemoryRateLimiter", "RateLimit"]
