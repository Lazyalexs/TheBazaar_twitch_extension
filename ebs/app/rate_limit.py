from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class InMemoryRateLimiter:
    min_interval_seconds: float
    _last_seen: dict[str, float] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def allow(self, key: str, now: float | None = None) -> tuple[bool, float]:
        current = time.monotonic() if now is None else now
        with self._lock:
            last = self._last_seen.get(key)
            if last is None:
                self._last_seen[key] = current
                return True, 0.0

            retry_after = self.min_interval_seconds - (current - last)
            if retry_after > 0:
                return False, retry_after

            self._last_seen[key] = current
            return True, 0.0

