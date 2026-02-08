# Financial Markets Dashboard

A full-stack financial dashboard that visualizes the S&P 500 and its sectors using interactive heatmaps, with tile sizing weighted by market capitalization and drill-down company analytics.

This project is designed with strict API-safety in mind and works within the Finnhub free API tier.

---

## Overview

The Financial Markets Dashboard provides an interactive view of the S&P 500 and its sector composition. Market performance is visualized through heatmaps where each tile represents a company, colored by daily performance and sized by market capitalization. Users can drill down into individual companies to view detailed metrics.

The backend is built using FastAPI and is carefully designed to minimize API usage through caching, rate limiting, and on-demand data fetching. The frontend is built with React and Vite and focuses on a clean, modern, and responsive user experience.

---

## Features

- S&P 500 overview heatmap
- Sector-level heatmaps with tabbed navigation
- Market-cap weighted heatmap tiles
- Daily performance coloring by percentage change
- Interactive tooltips and company detail drawer
- Strict rate-limit and cache management for Finnhub free tier
- Graceful fallback to cached or stale data

---

## Tech Stack

### Backend
- Python
- FastAPI
- httpx
- python-dotenv
- Uvicorn

### Frontend
- React
- Vite
- TypeScript
- TailwindCSS
- Nivo Treemap
- Framer Motion

---

## Project Structure

Financial-Markets-Dashboard/
├── backend/
│   ├── app.py
│   ├── finnhub_client.py
│   ├── cache.py
│   ├── limiter.py
│   ├── data/
│   │   └── sp500_constituents.json
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   ├── vite.config.ts
│   └── package.json
└── README.md

---

## Backend Setup

### Create and Activate Virtual Environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Create a `.env` file in the backend directory:

```env
FINNHUB_API_KEY=YOUR_FINNHUB_API_KEY
```

### Run Backend Server

```bash
uvicorn app:app --reload --port 8001
```

Verify the server is running by visiting:

http://127.0.0.1:8001/health

---

## Frontend Setup

### Install Dependencies

```bash
cd frontend
npm install
```

### Configure API Proxy (Recommended)

In `frontend/vite.config.ts`, configure a proxy so the frontend can communicate with the backend:

```ts
server: {
  proxy: {
    '/api': 'http://127.0.0.1:8001',
    '/health': 'http://127.0.0.1:8001',
  },
},
```

### Run Frontend Development Server

```bash
npm run dev
```

Open the application at:

http://localhost:5173

---

## Data Flow

1. The backend loads S&P 500 constituents from a local dataset.
2. Market data is fetched from Finnhub only when requested.
3. Quote data is cached using a time-to-live strategy to minimize API calls.
4. The frontend requests sector data only when a sector tab is selected.
5. Heatmaps render using market capitalization for tile sizing and daily performance for coloring.

---

## API Endpoints

- GET /health
- GET /api/index
- GET /api/sectors
- GET /api/sector/{sector}?limit=80
- GET /api/subsector/{sector}/{subIndustry}
- GET /api/search?q=

---

## Finnhub Free Tier Considerations

- Approximately 60 API calls per minute supported
- No background polling
- On-demand sector loading
- In-memory caching with stale fallback
- Safe for repeated tab switching without exceeding rate limits

---

## Roadmap

- Historical price charts
- Market-cap versus equal-weight sizing toggle
- Dark and light theme toggle
- Search and filtering within heatmaps
- Production deployment configuration

---

## License

MIT License

---

## Author

Flynn Peters  
GitHub: https://github.com/FlynnPeters15
