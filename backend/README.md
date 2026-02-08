# Financial Dashboard API (Backend)

FastAPI service that powers a financial dashboard using the [Finnhub API](https://finnhub.io), with strict call-limiting for free-tier usage.

## Setup

### 1. Finnhub API key

Get a free API key from [Finnhub](https://finnhub.io/register) and set it in your environment:

**Windows (PowerShell):**
```powershell
$env:FINNHUB_API_KEY = "your-api-key-here"
```

**Windows (Command Prompt):**
```cmd
set FINNHUB_API_KEY=your-api-key-here
```

**Linux / macOS:**
```bash
export FINNHUB_API_KEY=your-api-key-here
```

### 2. Install dependencies

From the `backend` directory:

```bash
pip install -r requirements.txt
```

### 3. Run the server

```bash
uvicorn app:app --reload --port 8001
```

API base URL: `http://localhost:8001`

- Docs (Swagger): `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FINNHUB_API_KEY` | (required) | Finnhub API token |
| `QUOTE_CACHE_TTL_SECONDS` | `300` | TTL in seconds for in-memory quote cache (per symbol) |
| `FINNHUB_MAX_CALLS_PER_MIN` | `50` | Token-bucket cap: max outbound Finnhub calls per minute |
| `FINNHUB_MAX_CONCURRENT` | `5` | Max simultaneous outbound quote requests (semaphore) |
| `MAX_COMPANIES_PER_REQUEST` | `80` | Hard cap on `limit` for sector/subsector endpoints |

---

## Caching and rate limits

- **TTL cache:** Each symbol’s quote is cached in memory. Within the TTL (default 5 minutes), repeated requests for the same symbol do **not** call Finnhub. Use `QUOTE_CACHE_TTL_SECONDS` to tune.
- **Rate limiter:** A global token bucket limits how many Finnhub requests are made per minute (default 50). If the bucket is empty, the service either returns cached/stale data for that symbol (when available) or returns an error for that symbol; the response still includes `meta.rate_limited` and per-company `status`/`error` where applicable.
- **Concurrency:** An asyncio semaphore (default 5) caps how many quote requests are in flight at once to avoid bursts.
- **On-demand only:** Quotes are fetched only when an endpoint needs them (e.g. `/api/index`, `/api/sector/...`, `/api/subsector/...`). No bulk pre-fetch at startup.
- **Limit and cap:** Sector/subsector endpoints accept `?limit=N` (default 50, max set by `MAX_COMPANIES_PER_REQUEST`) to reduce the number of symbols requested per call.

Tuning for free tier: keep `FINNHUB_MAX_CALLS_PER_MIN` at or below 60, increase `QUOTE_CACHE_TTL_SECONDS` to reduce repeat calls, and use `limit` on sector/subsector to request fewer companies per request.

---

## Example requests

### Health

```bash
curl -s http://localhost:8001/health
```

### S&P 500 index (last close, SPY or ^GSPC)

```bash
curl -s http://localhost:8001/api/index
```

### List sectors (with counts)

```bash
curl -s http://localhost:8001/api/sectors
```

### List sub-industries for a sector

```bash
curl -s "http://localhost:8001/api/subsectors/Information%20Technology"
```

### Companies in a sector (with quotes)

```bash
curl -s "http://localhost:8001/api/sector/Information%20Technology?limit=10"
```

With refresh (bypass cache, still rate-limited):

```bash
curl -s "http://localhost:8001/api/sector/Information%20Technology?limit=10&refresh=true"
```

### Companies in a sub-industry

```bash
curl -s "http://localhost:8001/api/subsector/Information%20Technology/Semiconductors?limit=20"
```

### Search constituents (no Finnhub calls)

```bash
curl -s "http://localhost:8001/api/search?q=apple"
```

---

## Data: S&P 500 constituents

Constituents (symbol, name, sector, sub-industry) are read from:

```
backend/data/sp500_constituents.json
```

The repo includes a starter set (150+ names across sectors). You can replace this file with a full S&P 500 list; the same schema is expected:

```json
{
  "symbol": "AAPL",
  "name": "Apple Inc",
  "sector": "Information Technology",
  "subIndustry": "Technology Hardware, Storage & Peripherals"
}
```

Quotes (last close, previous close, change, etc.) are fetched from Finnhub only when required by the endpoints above, subject to caching and rate limits.
