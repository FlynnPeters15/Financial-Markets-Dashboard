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
        self._total_acquired = 0
        self._total_denied = 0
        logger.info("TokenBucketLimiter initialized: max=%d calls/min", self._max)

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
                self._total_acquired += 1
                logger.debug("Token acquired: remaining=%.2f/%d", self._tokens, self._max)
                return True
            self._total_denied += 1
            logger.warning("Rate limit: tokens=%.2f/%d, denied=%d", self._tokens, self._max, self._total_denied)
            return False

    async def get_stats(self) -> dict:
        """Return current limiter statistics for logging/debugging."""
        async with self._lock:
            self._refill()
            return {
                "tokens_remaining": round(self._tokens, 2),
                "max_tokens": self._max,
                "total_acquired": self._total_acquired,
                "total_denied": self._total_denied,
            }


# Singleton
_limiter: Optional[TokenBucketLimiter] = None


def get_rate_limiter() -> TokenBucketLimiter:
    global _limiter
    if _limiter is None:
        _limiter = TokenBucketLimiter()
    return _limiter
