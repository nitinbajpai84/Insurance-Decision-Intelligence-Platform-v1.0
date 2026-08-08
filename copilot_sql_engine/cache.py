from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


_CACHE: dict[str, CacheEntry] = {}


def cache_get_or_set(key: str, factory: Callable[[], Any], ttl_seconds: int = 900) -> tuple[Any, bool, int]:
    start = time.perf_counter()
    now = time.time()
    entry = _CACHE.get(key)
    if entry and entry.expires_at > now:
        return entry.value, True, int((time.perf_counter() - start) * 1000)
    value = factory()
    _CACHE[key] = CacheEntry(value=value, expires_at=now + ttl_seconds)
    return value, False, int((time.perf_counter() - start) * 1000)


def clear_cache() -> None:
    _CACHE.clear()
