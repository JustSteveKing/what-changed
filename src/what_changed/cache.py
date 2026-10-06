import time
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


# A small in-memory cache with a fixed time to live. It lives as long as the
# process, so it helps a long-running caller (or an eval run), not one-off CLI calls.
class TtlCache(Generic[T]):
    def __init__(self, ttl_s: float, now: Callable[[], float] = time.monotonic) -> None:
        self._ttl_s = ttl_s
        self._now = now
        self._entries: dict[str, tuple[T, float]] = {}

    def get(self, key: str) -> T | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at <= self._now():
            del self._entries[key]
            return None
        return value

    def set(self, key: str, value: T) -> None:
        if self._ttl_s <= 0:
            return
        self._entries[key] = (value, self._now() + self._ttl_s)
