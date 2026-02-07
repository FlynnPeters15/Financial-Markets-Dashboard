"""FastAPI application for financial dashboard (Finnhub, rate-limited)."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import finnhub_client
from data_loader import (
    get_constituents_by_sector,
    get_constituents_by_subsector,
    get_sectors_with_counts,
    get_subsectors_for_sector,
    load_constituents,
    search_constituents,
)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    if limit is None:
        return DEFAULT_LIMIT
    return min(max(1, int(limit)), MAX_COMPANIES_PER_REQUEST)


def _company_quote_from_result(
    symbol: str,
    name: str,
    sub_industry: str,
    result: dict,
    source: str,
) -> CompanyQuote:
    if result.get("status") == "error":
        return CompanyQuote(
            symbol=symbol,
            name=name,
            subIndustry=sub_industry,
            status="error",
            error=result.get("error"),
            source=source,
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
    """Last trading day close for S&P 500: try ^GSPC first, fallback to SPY."""
    symbol = "^GSPC"
    payload, source = await finnhub_client.get_quote("^GSPC", use_cache=True, refresh=False)
    if payload.get("status") == "error":
        logger.info("^GSPC failed (%s), falling back to SPY", payload.get("error"))
        symbol = "SPY"
        payload, source = await finnhub_client.get_quote("SPY", use_cache=True, refresh=False)

    if payload.get("status") == "error":
        raise HTTPException(
            status_code=503,
            detail={"reason": payload.get("error", "quote unavailable"), "symbol": symbol},
        )

    name = "S&P 500 (proxy)" if symbol == "SPY" else "S&P 500"
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
    """Companies in sector with last close; optional limit and refresh."""
    constituents = get_constituents_by_sector(_constituents_list(), sector)
    if not constituents:
        raise HTTPException(status_code=404, detail=f"Sector not found: {sector}")

    cap = _cap_limit(limit)
    to_fetch = constituents[:cap]
    requested = len(to_fetch)

    cache = get_quote_cache()
    cache_hits = 0
    api_calls = 0
    rate_limited = False
    companies_out = []
    now_utc = _utc_now()

    for c in to_fetch:
        payload, source = await finnhub_client.get_quote(
            c.symbol, use_cache=True, refresh=refresh
        )
        if source in ("cache", "stale_cache"):
            cache_hits += 1
        else:
            api_calls += 1
        if payload.get("status") == "error" and payload.get("error") == "rate_limited":
            rate_limited = True
        companies_out.append(
            _company_quote_from_result(
                c.symbol, c.name, c.subIndustry, payload, source
            )
        )

    if rate_limited and cache_hits == 0 and all(co.status == "error" for co in companies_out):
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
            cache_hits=cache_hits,
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
    """Companies in sector + sub-industry with last close."""
    constituents = get_constituents_by_subsector(
        _constituents_list(), sector, sub_industry
    )
    if not constituents:
        raise HTTPException(
            status_code=404,
            detail=f"Sub-industry not found: {sector} / {sub_industry}",
        )

    cap = _cap_limit(limit)
    to_fetch = constituents[:cap]
    requested = len(to_fetch)

    cache_hits = 0
    api_calls = 0
    rate_limited = False
    companies_out = []
    now_utc = _utc_now()

    for c in to_fetch:
        payload, source = await finnhub_client.get_quote(
            c.symbol, use_cache=True, refresh=refresh
        )
        if source in ("cache", "stale_cache"):
            cache_hits += 1
        else:
            api_calls += 1
        if payload.get("status") == "error" and payload.get("error") == "rate_limited":
            rate_limited = True
        companies_out.append(
            _company_quote_from_result(
                c.symbol, c.name, c.subIndustry, payload, source
            )
        )

    if rate_limited and cache_hits == 0 and all(co.status == "error" for co in companies_out):
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
            cache_hits=cache_hits,
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
