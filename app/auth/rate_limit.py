"""In-process login rate limiting."""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from app.auth.settings import auth_settings


class LoginRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = defaultdict(list)

    def _key(self, client_ip: str, identifier: str) -> str:
        return f"{client_ip}|{identifier.strip().lower()}"

    def _prune(self, key: str, now: float, window: int) -> None:
        self._failures[key] = [t for t in self._failures[key] if now - t < window]

    def is_blocked(self, client_ip: str, identifier: str) -> bool:
        settings = auth_settings()
        key = self._key(client_ip, identifier)
        now = time.monotonic()
        with self._lock:
            self._prune(key, now, settings.login_window_seconds)
            return len(self._failures[key]) >= settings.login_max_failures

    def record_failure(self, client_ip: str, identifier: str) -> None:
        settings = auth_settings()
        key = self._key(client_ip, identifier)
        now = time.monotonic()
        with self._lock:
            self._prune(key, now, settings.login_window_seconds)
            self._failures[key].append(now)

    def clear(self, client_ip: str, identifier: str) -> None:
        key = self._key(client_ip, identifier)
        with self._lock:
            self._failures.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


login_rate_limiter = LoginRateLimiter()
