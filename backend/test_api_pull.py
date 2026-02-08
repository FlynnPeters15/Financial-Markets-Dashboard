"""
Test script: pull S&P 500 and 11 sector ETF prices via Finnhub to verify API is working.

Run from the backend directory:
    python test_api_pull.py

Requires FINNHUB_API_KEY in the environment (e.g. .env or export).
"""

import asyncio
import os
import sys

# Ensure backend is on path when run from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path


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

import finnhub_client

# S&P 500: Finnhub uses ^GSPC; fallback to SPY if needed
SP500_SYMBOL = "^GSPC"
SP500_NAME = "S&P 500"

# 11 GICS sector ETFs (SPDR Select Sector)
SECTOR_ETFS = [
    ("XLK", "Technology"),
    ("XLF", "Financials"),
    ("XLV", "Health Care"),
    ("XLE", "Energy"),
    ("XLY", "Consumer Discretionary"),
    ("XLP", "Consumer Staples"),
    ("XLI", "Industrials"),
    ("XLB", "Materials"),
    ("XLU", "Utilities"),
    ("XLRE", "Real Estate"),
    ("XLC", "Communication Services"),
]


async def fetch_all():
    """Fetch S&P 500 then all 11 sector ETFs; print results."""
    if not os.environ.get("FINNHUB_API_KEY", "").strip():
        print("ERROR: FINNHUB_API_KEY is not set. Set it in .env or export it.")
        return

    print("Testing Finnhub API pull: S&P 500 + 11 sector ETFs")
    print("=" * 60)

    # 1) S&P 500
    symbol = SP500_SYMBOL
    payload, source = await finnhub_client.get_quote(symbol, use_cache=True, refresh=True)
    if payload.get("status") == "error":
        print(f"  {SP500_NAME} ({symbol}): FAILED - {payload.get('error', 'unknown')}")
        symbol = "SPY"
        payload, source = await finnhub_client.get_quote("SPY", use_cache=True, refresh=True)
        if payload.get("status") == "error":
            print(f"  S&P 500 fallback (SPY): FAILED - {payload.get('error', 'unknown')}")
        else:
            _print_quote("S&P 500 (SPY proxy)", payload, source)
    else:
        _print_quote(SP500_NAME, payload, source)

    print()

    # 2) 11 sector ETFs
    for sym, name in SECTOR_ETFS:
        payload, source = await finnhub_client.get_quote(sym, use_cache=True, refresh=True)
        if payload.get("status") == "error":
            print(f"  {name} ({sym}): FAILED - {payload.get('error', 'unknown')}")
        else:
            _print_quote(f"{name} ({sym})", payload, source)

    print("=" * 60)
    print("Done.")


def _print_quote(label: str, payload: dict, source: str):
    close = payload.get("close", 0)
    prev = payload.get("prevClose", 0)
    chg = payload.get("change", 0)
    pct = payload.get("pctChange", 0)
    print(f"  {label}: close={close:.2f}  prevClose={prev:.2f}  change={chg:+.2f}  pctChange={pct:+.2f}%  [source={source}]")


if __name__ == "__main__":
    asyncio.run(fetch_all())
