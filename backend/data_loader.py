"""Load and query S&P 500 constituents from local JSON."""

import json
import logging
from pathlib import Path
from typing import Optional

from models import Constituent

logger = logging.getLogger(__name__)

# Default path relative to this file
DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "sp500_constituents.json"


def load_constituents(path: Optional[Path] = None) -> list[Constituent]:
    """Load constituents from JSON file. Returns empty list on error."""
    p = path or DEFAULT_DATA_PATH
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            return [Constituent(**item) for item in raw]
        if isinstance(raw, dict) and "constituents" in raw:
            return [Constituent(**item) for item in raw["constituents"]]
        return []
    except Exception as e:
        logger.exception("Failed to load constituents from %s: %s", p, e)
        return []


def get_constituents_by_sector(
    constituents: list[Constituent], sector: str
) -> list[Constituent]:
    """Return constituents in the given sector (case-insensitive match)."""
    sector_lower = sector.strip().lower()
    return [c for c in constituents if c.sector.lower() == sector_lower]


def get_constituents_by_subsector(
    constituents: list[Constituent], sector: str, sub_industry: str
) -> list[Constituent]:
    """Return constituents in the given sector and sub-industry."""
    sector_list = get_constituents_by_sector(constituents, sector)
    sub_lower = sub_industry.strip().lower()
    return [c for c in sector_list if c.subIndustry.lower() == sub_lower]


def get_sectors_with_counts(constituents: list[Constituent]) -> list[dict]:
    """Return list of {sector, count, subIndustryCount}."""
    from collections import defaultdict

    sector_to_constituents: dict[str, list[Constituent]] = defaultdict(list)
    for c in constituents:
        sector_to_constituents[c.sector].append(c)

    result = []
    for sector, members in sorted(sector_to_constituents.items()):
        sub_industries = {c.subIndustry for c in members}
        result.append(
            {
                "sector": sector,
                "count": len(members),
                "subIndustryCount": len(sub_industries),
            }
        )
    return result


def get_subsectors_for_sector(
    constituents: list[Constituent], sector: str
) -> list[dict]:
    """Return list of {subIndustry, count} for the given sector."""
    sector_list = get_constituents_by_sector(constituents, sector)
    from collections import Counter

    counts = Counter(c.subIndustry for c in sector_list)
    return [{"subIndustry": sub, "count": n} for sub, n in sorted(counts.items())]


def search_constituents(
    constituents: list[Constituent], query: str, limit: int = 50
) -> list[Constituent]:
    """Search by symbol or name (case-insensitive). No Finnhub calls."""
    q = (query or "").strip().lower()
    if not q:
        return []
    matches = []
    for c in constituents:
        if q in c.symbol.lower() or q in c.name.lower():
            matches.append(c)
        if len(matches) >= limit:
            break
    return matches
