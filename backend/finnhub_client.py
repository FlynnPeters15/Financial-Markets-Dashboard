"""Finnhub API client with rate limiting, caching, and concurrency cap."""

import asyncio
import logging
import os
from typing import Any, Optional

import httpx

from cache import get_quote_cache
from limiter import get_rate_limiter

logger = logging.getLogger(__name__)

FINNHUB_BASE_URL = "https://api.finnhub.io"
FINNHUB_QUOTE_PATH = "/api/v1/quote"
DEFAULT_MAX_CONCURRENT = int(os.environ.get("FINNHUB_MAX_CONCURRENT", "5"))

# Global semaphore for concurrent quote requests
_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(DEFAULT_MAX_CONCURRENT)
    return _semaphore


def _parse_quote_response(data: dict, symbol: str) -> dict[str, Any]:
    """Build normalized quote dict: close, prevClose, open, high, low, change, pctChange."""
    c = float(data.get("c") or 0)
    pc = float(data.get("pc") or 0)
    o = float(data.get("o") or 0)
    h = float(data.get("h") or 0)
    l = float(data.get("l") or 0)
    change = c - pc if pc is not None else 0.0
    pct_change = (change / pc * 100) if pc and pc != 0 else 0.0
    return {
        "close": c,
        "prevClose": pc,
        "open": o,
        "high": h,
        "low": l,
        "change": change,
        "pctChange": round(pct_change, 4),
    }


async def fetch_quote(symbol: str) -> dict[str, Any]:
    """
    Fetch quote from Finnhub with retries (2 retries, exponential backoff for 5xx/timeouts).
    Returns dict with close, prevClose, open, high, low, change, pctChange, or error fields.
    """
    api_key = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not api_key:
        return {"status": "error", "error": "FINNHUB_API_KEY not set"}

    url = f"{FINNHUB_BASE_URL}{FINNHUB_QUOTE_PATH}"
    params = {"symbol": symbol, "token": api_key}

    sem = _get_semaphore()
    async with sem:
        for attempt in range(3):  # 1 initial + 2 retries
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url, params=params)
                if resp.status_code == 429:
                    return {"status": "error", "error": "rate_limited"}
                if resp.status_code >= 500 or resp.status_code in (408, 429):
                    if attempt < 2:
                        await asyncio.sleep(2**attempt)
                        continue
                    return {"status": "error", "error": f"HTTP {resp.status_code}"}
                if resp.status_code != 200:
                    return {"status": "error", "error": f"HTTP {resp.status_code}"}
                data = resp.json()
                if isinstance(data, dict) and "c" in data:
                    return _parse_quote_response(data, symbol)
                return {"status": "error", "error": "invalid response"}
            except httpx.TimeoutException:
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
                    continue
                return {"status": "error", "error": "timeout"}
            except Exception as e:
                logger.exception("Quote fetch failed for %s: %s", symbol, e)
                return {"status": "error", "error": str(e)}
    return {"status": "error", "error": "unknown"}


async def get_quote(
    symbol: str,
    *,
    use_cache: bool = True,
    refresh: bool = False,
) -> tuple[dict[str, Any], str]:
    """
    Get quote for symbol: check cache first (unless refresh), then rate limit, then fetch.
    Returns (payload, source) where source is "finnhub" | "cache" | "stale_cache".
    Payload includes close, prevClose, ... or status/error.
    """
    cache = get_quote_cache()
    limiter = get_rate_limiter()
    key = f"quote:{symbol.upper()}"

    if use_cache and not refresh:
        cached = cache.get(key)
        if cached:
            value, source = cached
            return (value, source)

    allowed = await limiter.acquire()
    if not allowed:
        # Prefer stale cache over failing
        stale = cache.get(key)
        if stale:
            value, _ = stale
            logger.info("Rate limited; serving stale cache for %s", symbol)
            return (value, "stale_cache")
        return (
            {"status": "error", "error": "rate_limited", "symbol": symbol},
            "error",
        )

    result = await fetch_quote(symbol)
    if "status" not in result or result.get("status") != "error":
        cache.set(key, result)
        logger.info("Quote for %s from finnhub (API call)", symbol)
        return (result, "finnhub")
    logger.warning("Quote for %s failed: %s", symbol, result.get("error"))
    return (result, "finnhub")
