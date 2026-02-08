"""TTL cache for quote responses with optional stale fallback."""

import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_TTL = int(os.environ.get("QUOTE_CACHE_TTL_SECONDS", "300"))


class QuoteCache:
    """In-memory TTL cache. Stores (value, expiry_ts). Serves stale if requested."""

    def __init__(self, ttl_seconds: Optional[int] = None):
        self._ttl = ttl_seconds if ttl_seconds is not None else DEFAULT_TTL
        self._store: dict[str, tuple[Any, float]] = {}
        self._hits_fresh = 0
        self._hits_stale = 0
        self._misses = 0
        self._sets = 0
        logger.info("QuoteCache initialized: TTL=%d seconds", self._ttl)

    def get(self, key: str) -> Optional[tuple[Any, str]]:
        """
        Get cached value for key.
        Returns (value, source) where source is "cache" or "stale_cache", or None if not found.
        """
        entry = self._store.get(key)
        if not entry:
            self._misses += 1
            logger.debug("Quote cache MISS for %s", key)
            return None
        value, expiry = entry
        now = time.monotonic()
        if now <= expiry:
            self._hits_fresh += 1
            logger.debug("Quote cache HIT (fresh) for %s", key)
            return (value, "cache")
        # Expired but we have stale data
        self._hits_stale += 1
        logger.debug("Quote cache HIT (stale) for %s", key)
        return (value, "stale_cache")

    def set(self, key: str, value: Any) -> None:
        """Store value with TTL from now."""
        expiry = time.monotonic() + self._ttl
        self._store[key] = (value, expiry)
        self._sets += 1
        logger.debug("Quote cache SET for %s (expires in %d seconds)", key, self._ttl)

    def delete(self, key: str) -> None:
        """Remove key from cache."""
        self._store.pop(key, None)
        logger.debug("Quote cache DELETE for %s", key)

    def get_stats(self) -> dict:
        """Return cache statistics for logging/debugging."""
        return {
            "size": len(self._store),
            "hits_fresh": self._hits_fresh,
            "hits_stale": self._hits_stale,
            "misses": self._misses,
            "sets": self._sets,
            "ttl_seconds": self._ttl,
        }

    @property
    def ttl_seconds(self) -> int:
        return self._ttl


# Singleton used by app and finnhub_client
quote_cache: Optional["QuoteCache"] = None


def get_quote_cache() -> QuoteCache:
    global quote_cache
    if quote_cache is None:
        quote_cache = QuoteCache()
    return quote_cache
