from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


class RetryableEmbeddingError(RuntimeError):
    """Raised when an embedding request should be retried."""


def is_non_retryable_provider_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    non_retryable_markers = [
        "prepayment credits are depleted",
        "billing",
        "permission_denied",
        "permission denied",
        "unauthenticated",
        "api key",
        "invalid api",
        "forbidden",
        "access denied",
        "project has been denied access",
    ]
    return any(marker in message for marker in non_retryable_markers)


def with_retry(
    fn: Callable[[], T],
    *,
    attempts: int,
    base_seconds: float,
    retryable: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retryable as exc:
            last_error = exc
            if is_non_retryable_provider_error(exc):
                raise RuntimeError(f"Operation failed with non-retryable provider error: {exc}") from exc
            if attempt == attempts:
                break
            jitter = random.uniform(0, base_seconds)
            sleep_for = min(60.0, base_seconds * (2 ** (attempt - 1)) + jitter)
            print(f"Retryable error on attempt {attempt}/{attempts}: {exc}. Sleeping {sleep_for:.1f}s.")
            time.sleep(sleep_for)
    raise RuntimeError(f"Operation failed after {attempts} attempts") from last_error
