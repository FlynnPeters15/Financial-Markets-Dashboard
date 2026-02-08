"""Pydantic models for the financial dashboard API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Constituent (from local JSON) ---
class Constituent(BaseModel):
    symbol: str
    name: str
    sector: str
    subIndustry: str


# --- Index (S&P 500 proxy) ---
class IndexResponse(BaseModel):
    symbol: str
    name: str
    close: float
    prevClose: float
    change: float
    pctChange: float
    ts: datetime
    source: str  # "finnhub" | "cache" | "stale_cache"


# --- Sector list ---
class SectorSummary(BaseModel):
    sector: str
    count: int
    subIndustryCount: int


# --- Sub-industry list ---
class SubIndustrySummary(BaseModel):
    subIndustry: str
    count: int


# --- Company quote (for sector/subsector responses) ---
class CompanyQuote(BaseModel):
    symbol: str
    name: str
    subIndustry: str
    close: float = 0.0
    prevClose: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    change: float = 0.0
    pctChange: float = 0.0
    status: str = "ok"  # "ok" | "error"
    error: Optional[str] = None
    source: str = "finnhub"  # "finnhub" | "cache" | "stale_cache"


# --- Sector/Subsector response meta ---
class SectorMeta(BaseModel):
    requested: int
    returned: int
    cache_hits: int
    api_calls: int
    rate_limited: bool


# --- Sector/Subsector response ---
class SectorResponse(BaseModel):
    sector: str
    updated_at: datetime
    companies: list[CompanyQuote]
    meta: SectorMeta


# --- Health ---
class HealthResponse(BaseModel):
    ok: bool
    ts: datetime
    version: str


# --- Search result ---
class SearchResult(BaseModel):
    symbol: str
    name: str
    sector: str
    subIndustry: str
