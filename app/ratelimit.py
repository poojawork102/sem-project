"""Tiny in-memory sliding-window rate limiter, easy to explain in a viva.

Each key (e.g. a client IP) keeps a list of recent event timestamps; events older
than the window are dropped, and the key is blocked once it holds `max_events`.
Limitation: state lives in this process only, so it resets on restart and is not
shared between workers. Behind a reverse proxy, request.client.host is the proxy's
IP unless the proxy is configured to forward the real client address.
"""
import threading
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_events: int, window_seconds: int):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _recent(self, key: str) -> list[float]:
        cutoff = time.monotonic() - self.window_seconds
        recent = [t for t in self._events.get(key, []) if t > cutoff]
        if recent:
            self._events[key] = recent
        else:
            # Drop idle keys so the dict cannot grow forever with one entry per IP ever seen.
            self._events.pop(key, None)
        return recent

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key)) >= self.max_events

    def record(self, key: str) -> None:
        with self._lock:
            self._recent(key)
            self._events[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
