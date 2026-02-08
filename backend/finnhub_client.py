"""Finnhub API client with rate limiting, caching, and concurrency cap.

This is the CENTRALIZED API CLIENT - all Finnhub calls must go through this module.
All requests pass through:
- rate limiter (token bucket)
- concurrency limiter (semaphore)
- cache layer (TTL-based)
"""

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
FINNHUB_PROFILE_PATH = "/api/v1/stock/profile2"
DEFAULT_MAX_CONCURRENT = int(os.environ.get("FINNHUB_MAX_CONCURRENT", "5"))
DEFAULT_TIMEOUT = float(os.environ.get("FINNHUB_TIMEOUT_SECONDS", "15.0"))
MAX_RETRIES = 2  # Maximum 2 retries (3 total attempts)

# Global semaphore for concurrent quote requests
_semaphore: Optional[asyncio.Semaphore] = None
_api_call_count = 0  # Track total API calls for logging


def _get_semaphore() -> asyncio.Semaphore:
    """Get or create the global semaphore for concurrency control."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(DEFAULT_MAX_CONCURRENT)
        logger.info("Concurrency semaphore initialized: max_concurrent=%d", DEFAULT_MAX_CONCURRENT)
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


async def fetch_company_profile(symbol: str) -> dict[str, Any]:
    """
    Fetch company profile from Finnhub to get market cap.
    Returns dict with marketCap (in USD) or error fields.
    """
    global _api_call_count
    api_key = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not api_key:
        logger.error("FINNHUB_API_KEY not set")
        return {"status": "error", "error": "FINNHUB_API_KEY not set"}

    url = f"{FINNHUB_BASE_URL}{FINNHUB_PROFILE_PATH}"
    params = {"symbol": symbol, "token": api_key}

    sem = _get_semaphore()
    async with sem:
        logger.debug("Acquired semaphore for profile %s (concurrent requests limited to %d)", symbol, DEFAULT_MAX_CONCURRENT)
        for attempt in range(MAX_RETRIES + 1):
            try:
                _api_call_count += 1
                logger.debug("Fetching company profile for %s (attempt %d/%d)", symbol, attempt + 1, MAX_RETRIES + 1)
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    resp = await client.get(url, params=params)
                
                # HTTP 429: Rate limited - NEVER retry
                if resp.status_code == 429:
                    logger.warning("HTTP 429 (rate limited) for profile %s - NOT retrying", symbol)
                    return {"status": "error", "error": "rate_limited"}
                
                # HTTP 5xx or 408: Retry with exponential backoff
                if resp.status_code >= 500 or resp.status_code == 408:
                    if attempt < MAX_RETRIES:
                        backoff = 2 ** attempt
                        logger.warning("HTTP %d for profile %s, retrying in %d seconds (attempt %d/%d)", 
                                     resp.status_code, symbol, backoff, attempt + 1, MAX_RETRIES + 1)
                        await asyncio.sleep(backoff)
                        continue
                    logger.error("HTTP %d for profile %s after %d attempts", resp.status_code, symbol, MAX_RETRIES + 1)
                    return {"status": "error", "error": f"HTTP {resp.status_code}"}
                
                # Other non-200 status codes: Don't retry
                if resp.status_code != 200:
                    logger.warning("HTTP %d for profile %s - not retrying", resp.status_code, symbol)
                    return {"status": "error", "error": f"HTTP {resp.status_code}"}
                
                # Parse successful response
                data = resp.json()
                if isinstance(data, dict):
                    # Market cap is in 'marketCapitalization' field (in USD)
                    market_cap = data.get("marketCapitalization")
                    if market_cap is not None:
                        try:
                            market_cap_float = float(market_cap)
                            logger.debug("Successfully fetched profile for %s, marketCap=%.2f", symbol, market_cap_float)
                            return {"marketCap": market_cap_float}
                        except (ValueError, TypeError):
                            logger.warning("Invalid marketCap value for %s: %s", symbol, market_cap)
                            return {"status": "error", "error": "invalid marketCap"}
                    # Market cap not available - not an error, just missing data
                    logger.debug("Market cap not available for %s", symbol)
                    return {"marketCap": None}
                logger.warning("Invalid response format for profile %s", symbol)
                return {"status": "error", "error": "invalid response"}
                
            except httpx.TimeoutException:
                if attempt < MAX_RETRIES:
                    backoff = 2 ** attempt
                    logger.warning("Timeout for profile %s, retrying in %d seconds (attempt %d/%d)", 
                                 symbol, backoff, attempt + 1, MAX_RETRIES + 1)
                    await asyncio.sleep(backoff)
                    continue
                logger.error("Timeout for profile %s after %d attempts", symbol, MAX_RETRIES + 1)
                return {"status": "error", "error": "timeout"}
            except Exception as e:
                logger.exception("Unexpected error fetching profile for %s: %s", symbol, e)
                return {"status": "error", "error": str(e)}
    
    logger.error("Failed to fetch profile for %s after all attempts", symbol)
    return {"status": "error", "error": "unknown"}


async def fetch_quote(symbol: str) -> dict[str, Any]:
    """
    Fetch quote from Finnhub with retries (max 2 retries, exponential backoff for 5xx/timeouts).
    NEVER retries on HTTP 429 (rate limit).
    
    Returns dict with close, prevClose, open, high, low, change, pctChange, or error fields.
    """
    global _api_call_count
    api_key = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not api_key:
        logger.error("FINNHUB_API_KEY not set")
        return {"status": "error", "error": "FINNHUB_API_KEY not set"}

    url = f"{FINNHUB_BASE_URL}{FINNHUB_QUOTE_PATH}"
    params = {"symbol": symbol, "token": api_key}

    sem = _get_semaphore()
    async with sem:
        logger.debug("Acquired semaphore for %s (concurrent requests limited to %d)", symbol, DEFAULT_MAX_CONCURRENT)
        for attempt in range(MAX_RETRIES + 1):  # 1 initial + MAX_RETRIES retries
            try:
                _api_call_count += 1
                logger.debug("Fetching quote for %s (attempt %d/%d)", symbol, attempt + 1, MAX_RETRIES + 1)
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    resp = await client.get(url, params=params)
                
                # HTTP 429: Rate limited - NEVER retry
                if resp.status_code == 429:
                    logger.warning("HTTP 429 (rate limited) for %s - NOT retrying", symbol)
                    return {"status": "error", "error": "rate_limited"}
                
                # HTTP 5xx or 408: Retry with exponential backoff
                if resp.status_code >= 500 or resp.status_code == 408:
                    if attempt < MAX_RETRIES:
                        backoff = 2 ** attempt
                        logger.warning("HTTP %d for %s, retrying in %d seconds (attempt %d/%d)", 
                                     resp.status_code, symbol, backoff, attempt + 1, MAX_RETRIES + 1)
                        await asyncio.sleep(backoff)
                        continue
                    logger.error("HTTP %d for %s after %d attempts", resp.status_code, symbol, MAX_RETRIES + 1)
                    return {"status": "error", "error": f"HTTP {resp.status_code}"}
                
                # Other non-200 status codes: Don't retry
                if resp.status_code != 200:
                    logger.warning("HTTP %d for %s - not retrying", resp.status_code, symbol)
                    return {"status": "error", "error": f"HTTP {resp.status_code}"}
                
                # Parse successful response
                data = resp.json()
                if isinstance(data, dict) and "c" in data:
                    logger.debug("Successfully fetched quote for %s", symbol)
                    return _parse_quote_response(data, symbol)
                logger.warning("Invalid response format for %s: missing 'c' field", symbol)
                return {"status": "error", "error": "invalid response"}
                
            except httpx.TimeoutException:
                if attempt < MAX_RETRIES:
                    backoff = 2 ** attempt
                    logger.warning("Timeout for %s, retrying in %d seconds (attempt %d/%d)", 
                                 symbol, backoff, attempt + 1, MAX_RETRIES + 1)
                    await asyncio.sleep(backoff)
                    continue
                logger.error("Timeout for %s after %d attempts", symbol, MAX_RETRIES + 1)
                return {"status": "error", "error": "timeout"}
            except Exception as e:
                logger.exception("Unexpected error fetching quote for %s: %s", symbol, e)
                # Don't retry on unexpected errors
                return {"status": "error", "error": str(e)}
    
    logger.error("Failed to fetch quote for %s after all attempts", symbol)
    return {"status": "error", "error": "unknown"}


async def get_quote(
    symbol: str,
    *,
    use_cache: bool = True,
    refresh: bool = False,
) -> tuple[dict[str, Any], str]:
    """
    Get quote for symbol: check cache first (unless refresh), then rate limit, then fetch.
    
    Flow:
    1. If use_cache=True and refresh=False: check cache (fresh or stale)
    2. If cache miss or refresh=True: check rate limiter
    3. If rate limited: return stale cache if available, else error
    4. If allowed: acquire semaphore, fetch from API, cache result
    
    Returns (payload, source) where source is:
    - "cache": fresh cached data
    - "stale_cache": expired cached data (served when rate limited)
    - "finnhub": live API response
    - "error": error occurred and no cache available
    
    Payload includes close, prevClose, ... or status/error.
    """
    cache = get_quote_cache()
    limiter = get_rate_limiter()
    key = f"quote:{symbol.upper()}"

    # Step 1: Check cache first (unless refresh is requested)
    if use_cache and not refresh:
        cached = cache.get(key)
        if cached:
            value, source = cached
            logger.debug("Quote for %s from %s (cache hit)", symbol, source)
            return (value, source)

    # Step 2: Cache miss or refresh requested - check rate limiter
    logger.debug("Cache miss or refresh requested for %s, checking rate limiter", symbol)
    allowed = await limiter.acquire()
    
    if not allowed:
        # Step 3: Rate limited - prefer stale cache over failing
        logger.warning("Rate limited for %s, checking for stale cache", symbol)
        stale = cache.get(key)
        if stale:
            value, _ = stale
            logger.info("Rate limited; serving stale cache for %s", symbol)
            return (value, "stale_cache")
        # No cache available at all
        stats = await limiter.get_stats()
        logger.error("Rate limited for %s with no cache available. Limiter stats: %s", symbol, stats)
        return (
            {"status": "error", "error": "rate_limited", "symbol": symbol},
            "error",
        )

    # Step 4: Rate limit allows - fetch from API
    logger.debug("Rate limit allows, fetching quote for %s from Finnhub", symbol)
    result = await fetch_quote(symbol)
    
    if "status" not in result or result.get("status") != "error":
        # Success - cache the result
        cache.set(key, result)
        logger.info("Quote for %s fetched from finnhub and cached", symbol)
        return (result, "finnhub")
    
    # API call failed - log and return error
    error_msg = result.get("error", "unknown error")
    logger.warning("Quote fetch failed for %s: %s", symbol, error_msg)
    return (result, "finnhub")


async def get_company_profile(
    symbol: str,
    *,
    use_cache: bool = True,
    refresh: bool = False,
) -> tuple[dict[str, Any], str]:
    """
    Get company profile for symbol: check cache first (unless refresh), then rate limit, then fetch.
    
    Returns (payload, source) where source is:
    - "cache": fresh cached data
    - "stale_cache": expired cached data (served when rate limited)
    - "finnhub": live API response
    - "error": error occurred and no cache available
    
    Payload includes marketCap or status/error.
    """
    cache = get_quote_cache()
    limiter = get_rate_limiter()
    key = f"profile:{symbol.upper()}"

    # Step 1: Check cache first (unless refresh is requested)
    if use_cache and not refresh:
        cached = cache.get(key)
        if cached:
            value, source = cached
            logger.debug("Profile for %s from %s (cache hit)", symbol, source)
            return (value, source)

    # Step 2: Cache miss or refresh requested - check rate limiter
    logger.debug("Cache miss or refresh requested for profile %s, checking rate limiter", symbol)
    allowed = await limiter.acquire()
    
    if not allowed:
        # Step 3: Rate limited - prefer stale cache over failing
        logger.warning("Rate limited for profile %s, checking for stale cache", symbol)
        stale = cache.get(key)
        if stale:
            value, _ = stale
            logger.info("Rate limited; serving stale cache for profile %s", symbol)
            return (value, "stale_cache")
        # No cache available at all
        stats = await limiter.get_stats()
        logger.error("Rate limited for profile %s with no cache available. Limiter stats: %s", symbol, stats)
        return (
            {"status": "error", "error": "rate_limited", "symbol": symbol},
            "error",
        )

    # Step 4: Rate limit allows - fetch from API
    logger.debug("Rate limit allows, fetching profile for %s from Finnhub", symbol)
    result = await fetch_company_profile(symbol)
    
    if "status" not in result or result.get("status") != "error":
        # Success - cache the result
        cache.set(key, result)
        logger.info("Profile for %s fetched from finnhub and cached", symbol)
        return (result, "finnhub")
    
    # API call failed - log and return error
    error_msg = result.get("error", "unknown error")
    logger.warning("Profile fetch failed for %s: %s", symbol, error_msg)
    return (result, "finnhub")


def get_api_call_count() -> int:
    """Get total number of API calls made (for logging/debugging)."""
    return _api_call_count
