"""Tiny in-memory sliding-window rate limiter (per user).

Good enough for a single server instance (our free-tier deployment). If the app ever
runs several instances, move this to the database or Redis.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> float | None:
        """Record a hit. Returns None if allowed, or seconds to wait if over the limit."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return round(self.window - (now - hits[0]), 1)
            hits.append(now)
            return None
