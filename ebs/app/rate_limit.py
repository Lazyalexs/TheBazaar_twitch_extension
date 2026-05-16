from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class InMemoryRateLimiter:
    min_interval_seconds: float
    cleanup_ttl_seconds: float = 60.0
    _last_seen: dict[str, float] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)
    _calls_since_cleanup: int = 0

    def allow(self, key: str, now: float | None = None) -> tuple[bool, float]:
        current = time.monotonic() if now is None else now
        with self._lock:
            self._calls_since_cleanup += 1
            if self._calls_since_cleanup >= 256:
                self._cleanup(current)
                self._calls_since_cleanup = 0

            last = self._last_seen.get(key)
            if last is None:
                self._last_seen[key] = current
                return True, 0.0

            retry_after = self.min_interval_seconds - (current - last)
            if retry_after > 0:
                return False, retry_after

            self._last_seen[key] = current
            return True, 0.0

    def _cleanup(self, now: float) -> None:
        """Remove entries whose last_seen is older than cleanup_ttl_seconds."""
        deadline = now - self.cleanup_ttl_seconds
        stale = [k for k, ts in self._last_seen.items() if ts < deadline]
        for k in stale:
            del self._last_seen[k]
