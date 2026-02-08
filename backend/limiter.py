"""Token bucket rate limiter for outbound Finnhub API calls."""

import asyncio
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MAX_CALLS_PER_MIN = int(os.environ.get("FINNHUB_MAX_CALLS_PER_MIN", "50"))


class TokenBucketLimiter:
    """Async token bucket: refill tokens at a fixed rate, consume one per call."""

    def __init__(self, max_calls_per_minute: Optional[int] = None):
        self._max = max_calls_per_minute if max_calls_per_minute is not None else DEFAULT_MAX_CALLS_PER_MIN
        self._tokens = float(self._max)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed_minutes = (now - self._last_refill) / 60.0
        self._tokens = min(
            self._max,
            self._tokens + elapsed_minutes * self._max,
        )
        self._last_refill = now

    async def acquire(self) -> bool:
        """
        Consume one token if available. Returns True if allowed, False if rate limited.
        """
        async with self._lock:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False


# Singleton
_limiter: Optional[TokenBucketLimiter] = None


def get_rate_limiter() -> TokenBucketLimiter:
    global _limiter
    if _limiter is None:
        _limiter = TokenBucketLimiter()
    return _limiter
