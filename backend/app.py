"""FastAPI application for financial dashboard (Finnhub, rate-limited)."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def load_env_file(env_path: str = ".env") -> None:
    """Load environment variables from .env file."""
    env_file = Path(env_path)
    if not env_file.exists():
        return
    
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    os.environ.setdefault(key, value)


# Load .env file if it exists
load_env_file()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import finnhub_client
from cache import get_quote_cache
from data_loader import (
    get_constituents_by_sector,
    get_constituents_by_subsector,
    get_sectors_with_counts,
    get_subsectors_for_sector,
    load_constituents,
    search_constituents,
)
from limiter import get_rate_limiter
from models import (
    CompanyQuote,
    HealthResponse,
    IndexResponse,
    SectorMeta,
    SectorResponse,
    SectorSummary,
    SubIndustrySummary,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"
DEFAULT_LIMIT = 50
MAX_COMPANIES_PER_REQUEST = int(os.environ.get("MAX_COMPANIES_PER_REQUEST", "80"))

app = FastAPI(title="Financial Dashboard API", version=APP_VERSION)

# Allowed origins for CORS
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


class OptionsHandlerMiddleware(BaseHTTPMiddleware):
    """Handle OPTIONS preflight requests before FastAPI validation.
    
    This middleware intercepts OPTIONS requests and returns 204 with CORS headers
    before FastAPI can validate query parameters or route the request.
    """
    
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            # Get origin from request
            origin = request.headers.get("origin")
            
            # Build CORS headers
            headers = {}
            if origin in ALLOWED_ORIGINS:
                headers["Access-Control-Allow-Origin"] = origin
                headers["Access-Control-Allow-Credentials"] = "true"
            
            # Get requested method and headers from preflight
            requested_method = request.headers.get("access-control-request-method", "GET, POST, PUT, DELETE, OPTIONS")
            requested_headers = request.headers.get("access-control-request-headers", "*")
            
            headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            headers["Access-Control-Allow-Headers"] = requested_headers
            headers["Access-Control-Max-Age"] = "86400"  # 24 hours
            
            # Return 204 No Content with CORS headers
            return Response(status_code=204, headers=headers)
        
        return await call_next(request)


# CORS middleware must be added immediately after app creation, before routes
# This handles CORS headers for non-OPTIONS requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add OPTIONS handler middleware AFTER CORSMiddleware so it runs FIRST
# (In Starlette, last middleware added runs first)
# This intercepts OPTIONS before FastAPI validation
app.add_middleware(OptionsHandlerMiddleware)

# Load constituents once at startup (read from disk only)
_constituents: list = []


@app.on_event("startup")
def startup():
    global _constituents
    _constituents = load_constituents()
    logger.info("Loaded %d constituents", len(_constituents))


def _constituents_list():
    return _constituents


# --- Helpers ---
def _cap_limit(limit: Optional[int]) -> int:
    """Cap limit to valid range [1, MAX_COMPANIES_PER_REQUEST]. Logs warning if capped."""
    if limit is None:
        return DEFAULT_LIMIT
    capped = min(max(1, int(limit)), MAX_COMPANIES_PER_REQUEST)
    if capped < int(limit):
        logger.warning("Request limit %d capped to %d (max allowed: %d)", limit, capped, MAX_COMPANIES_PER_REQUEST)
    return capped


def _company_quote_from_result(
    symbol: str,
    name: str,
    sub_industry: str,
    result: dict,
    source: str,
    market_cap: Optional[float] = None,
) -> CompanyQuote:
    if result.get("status") == "error":
        return CompanyQuote(
            symbol=symbol,
            name=name,
            subIndustry=sub_industry,
            status="error",
            error=result.get("error"),
            source=source,
            marketCap=market_cap,
        )
    return CompanyQuote(
        symbol=symbol,
        name=name,
        subIndustry=sub_industry,
        close=result.get("close", 0.0),
        prevClose=result.get("prevClose", 0.0),
        open=result.get("open", 0.0),
        high=result.get("high", 0.0),
        low=result.get("low", 0.0),
        change=result.get("change", 0.0),
        pctChange=result.get("pctChange", 0.0),
        marketCap=market_cap,
        status="ok",
        source=source,
    )


# --- Routes ---
@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        ok=True,
        ts=_utc_now(),
        version=APP_VERSION,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)




@app.get("/api/index", response_model=IndexResponse)
async def get_index():
    """
    Last trading day close for S&P 500: try ^GSPC first, fallback to SPY.
    On-demand fetching only - no prefetching.
    """
    symbol = "^GSPC"
    logger.debug("Fetching index quote for ^GSPC")
    payload, source = await finnhub_client.get_quote("^GSPC", use_cache=True, refresh=False)
    if payload.get("status") == "error":
        logger.info("^GSPC failed (%s), falling back to SPY", payload.get("error"))
        symbol = "SPY"
        payload, source = await finnhub_client.get_quote("SPY", use_cache=True, refresh=False)

    if payload.get("status") == "error":
        logger.error("Index fetch failed for %s: %s", symbol, payload.get("error"))
        raise HTTPException(
            status_code=503,
            detail={"reason": payload.get("error", "quote unavailable"), "symbol": symbol},
        )

    name = "S&P 500 (proxy)" if symbol == "SPY" else "S&P 500"
    logger.info("Index quote for %s: source=%s, close=%.2f", symbol, source, payload.get("close", 0.0))
    return IndexResponse(
        symbol=symbol,
        name=name,
        close=payload.get("close", 0.0),
        prevClose=payload.get("prevClose", 0.0),
        change=payload.get("change", 0.0),
        pctChange=payload.get("pctChange", 0.0),
        ts=_utc_now(),
        source=source,
    )


@app.get("/api/sectors", response_model=list[SectorSummary])
def list_sectors():
    """List sectors with counts and sub-industry counts."""
    rows = get_sectors_with_counts(_constituents_list())
    return [SectorSummary(**r) for r in rows]


@app.get("/api/subsectors/{sector}", response_model=list[SubIndustrySummary])
def list_subsectors(sector: str):
    """List sub-industries within a sector with counts."""
    rows = get_subsectors_for_sector(_constituents_list(), sector)
    return [SubIndustrySummary(**r) for r in rows]


@app.get("/api/sector/{sector}", response_model=SectorResponse)
async def get_sector(
    sector: str,
    limit: Optional[int] = Query(None, ge=1, le=MAX_COMPANIES_PER_REQUEST),
    refresh: bool = Query(False),
):
    """
    Companies in sector with last close; optional limit and refresh.
    On-demand fetching only - no prefetching.
    """
    constituents = get_constituents_by_sector(_constituents_list(), sector)
    if not constituents:
        raise HTTPException(status_code=404, detail=f"Sector not found: {sector}")

    # Enforce per-request caps
    cap = _cap_limit(limit)
    to_fetch = constituents[:cap]
    requested = len(to_fetch)
    total_available = len(constituents)
    
    if requested < total_available:
        logger.info("Sector %s: capping request to %d symbols (total available: %d)", 
                   sector, requested, total_available)

    cache = get_quote_cache()
    limiter = get_rate_limiter()
    cache_hits = 0
    cache_hits_stale = 0
    api_calls = 0
    rate_limited = False
    companies_out = []
    now_utc = _utc_now()

    logger.info("Fetching sector %s: %d symbols requested (refresh=%s)", 
               sector, requested, refresh)

    # Process sequentially (sector-level batching)
    for c in to_fetch:
        payload, source = await finnhub_client.get_quote(
            c.symbol, use_cache=True, refresh=refresh
        )
        if source == "cache":
            cache_hits += 1
        elif source == "stale_cache":
            cache_hits_stale += 1
            rate_limited = True
        elif source == "finnhub":
            api_calls += 1
        if payload.get("status") == "error" and payload.get("error") == "rate_limited":
            rate_limited = True
        
        # Fetch market cap (non-blocking - if it fails, we still return quote data)
        market_cap = None
        try:
            profile_payload, profile_source = await finnhub_client.get_company_profile(
                c.symbol, use_cache=True, refresh=refresh
            )
            if profile_source == "finnhub":
                api_calls += 1
            if profile_payload.get("status") != "error":
                market_cap = profile_payload.get("marketCap")
        except Exception as e:
            logger.warning("Failed to fetch market cap for %s: %s", c.symbol, e)
        
        companies_out.append(
            _company_quote_from_result(
                c.symbol, c.name, c.subIndustry, payload, source, market_cap
            )
        )

    # Log summary
    limiter_stats = await limiter.get_stats()
    cache_stats = cache.get_stats()
    logger.info(
        "Sector %s fetch complete: requested=%d, cache_hits=%d (fresh=%d, stale=%d), "
        "api_calls=%d, rate_limited=%s, tokens_remaining=%.2f",
        sector, requested, cache_hits + cache_hits_stale, cache_hits, cache_hits_stale,
        api_calls, rate_limited, limiter_stats["tokens_remaining"]
    )

    if rate_limited and cache_hits == 0 and cache_hits_stale == 0 and all(co.status == "error" for co in companies_out):
        raise HTTPException(
            status_code=429,
            detail={
                "reason": "rate_limited",
                "message": "Finnhub rate limit exceeded; no cached data available. Retry later or increase QUOTE_CACHE_TTL_SECONDS.",
            },
        )

    return SectorResponse(
        sector=sector,
        updated_at=now_utc,
        companies=companies_out,
        meta=SectorMeta(
            requested=requested,
            returned=len(companies_out),
            cache_hits=cache_hits + cache_hits_stale,
            api_calls=api_calls,
            rate_limited=rate_limited,
        ),
    )


@app.get("/api/subsector/{sector}/{sub_industry}", response_model=SectorResponse)
async def get_subsector(
    sector: str,
    sub_industry: str,
    limit: Optional[int] = Query(None, ge=1, le=MAX_COMPANIES_PER_REQUEST),
    refresh: bool = Query(False),
):
    """
    Companies in sector + sub-industry with last close.
    On-demand fetching only - no prefetching.
    """
    constituents = get_constituents_by_subsector(
        _constituents_list(), sector, sub_industry
    )
    if not constituents:
        raise HTTPException(
            status_code=404,
            detail=f"Sub-industry not found: {sector} / {sub_industry}",
        )

    # Enforce per-request caps
    cap = _cap_limit(limit)
    to_fetch = constituents[:cap]
    requested = len(to_fetch)
    total_available = len(constituents)
    
    if requested < total_available:
        logger.info("Subsector %s/%s: capping request to %d symbols (total available: %d)", 
                   sector, sub_industry, requested, total_available)

    cache = get_quote_cache()
    limiter = get_rate_limiter()
    cache_hits = 0
    cache_hits_stale = 0
    api_calls = 0
    rate_limited = False
    companies_out = []
    now_utc = _utc_now()

    logger.info("Fetching subsector %s/%s: %d symbols requested (refresh=%s)", 
               sector, sub_industry, requested, refresh)

    # Process sequentially (sector-level batching)
    for c in to_fetch:
        payload, source = await finnhub_client.get_quote(
            c.symbol, use_cache=True, refresh=refresh
        )
        if source == "cache":
            cache_hits += 1
        elif source == "stale_cache":
            cache_hits_stale += 1
            rate_limited = True
        elif source == "finnhub":
            api_calls += 1
        if payload.get("status") == "error" and payload.get("error") == "rate_limited":
            rate_limited = True
        
        # Fetch market cap (non-blocking - if it fails, we still return quote data)
        market_cap = None
        try:
            profile_payload, profile_source = await finnhub_client.get_company_profile(
                c.symbol, use_cache=True, refresh=refresh
            )
            if profile_source == "finnhub":
                api_calls += 1
            if profile_payload.get("status") != "error":
                market_cap = profile_payload.get("marketCap")
        except Exception as e:
            logger.warning("Failed to fetch market cap for %s: %s", c.symbol, e)
        
        companies_out.append(
            _company_quote_from_result(
                c.symbol, c.name, c.subIndustry, payload, source, market_cap
            )
        )

    # Log summary
    limiter_stats = await limiter.get_stats()
    cache_stats = cache.get_stats()
    logger.info(
        "Subsector %s/%s fetch complete: requested=%d, cache_hits=%d (fresh=%d, stale=%d), "
        "api_calls=%d, rate_limited=%s, tokens_remaining=%.2f",
        sector, sub_industry, requested, cache_hits + cache_hits_stale, cache_hits, cache_hits_stale,
        api_calls, rate_limited, limiter_stats["tokens_remaining"]
    )

    if rate_limited and cache_hits == 0 and cache_hits_stale == 0 and all(co.status == "error" for co in companies_out):
        raise HTTPException(
            status_code=429,
            detail={
                "reason": "rate_limited",
                "message": "Finnhub rate limit exceeded; no cached data available. Retry later or increase QUOTE_CACHE_TTL_SECONDS.",
            },
        )

    return SectorResponse(
        sector=sector,
        updated_at=now_utc,
        companies=companies_out,
        meta=SectorMeta(
            requested=requested,
            returned=len(companies_out),
            cache_hits=cache_hits + cache_hits_stale,
            api_calls=api_calls,
            rate_limited=rate_limited,
        ),
    )


@app.get("/api/search", response_model=list)
def search(q: str = Query(..., min_length=1), limit: int = Query(50, ge=1, le=100)):
    """Search constituents by symbol or name. No Finnhub calls."""
    results = search_constituents(_constituents_list(), q, limit=limit)
    return [
        {"symbol": c.symbol, "name": c.name, "sector": c.sector, "subIndustry": c.subIndustry}
        for c in results
    ]


# Optional: return 429 when rate limited and no stale cache (handled inside get_quote by returning error in payload)
# So we don't need a separate 429 here unless we want to raise before iterating. Current design serves partial + meta.rate_limited.
