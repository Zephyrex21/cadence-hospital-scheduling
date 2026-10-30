"""Tiny in-process login throttle (failed attempts within a sliding window).

Good enough for a single API instance; a multi-instance deployment should back
this with Redis. Only *failed* logins count, and a success clears the key.
"""

from __future__ import annotations

import threading
import time

from app.core.errors import RateLimitError


class LoginThrottle:
    def __init__(self) -> None:
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _purge(self, key: str, window: float, now: float) -> list[float]:
        hits = [t for t in self._fails.get(key, []) if now - t < window]
        if hits:
            self._fails[key] = hits
        else:
            self._fails.pop(key, None)
        return hits

    def check(self, key: str, *, limit: int, window_sec: int) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._purge(key, window_sec, now)
            if len(hits) >= limit:
                retry = max(1, int(window_sec - (now - hits[0])))
                raise RateLimitError(
                    "Too many failed sign-in attempts. Try again later.", retry_after=retry
                )

    def fail(self, key: str) -> None:
        with self._lock:
            self._fails.setdefault(key, []).append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._fails.clear()


login_throttle = LoginThrottle()
