# Financial Markets Dashboard - Frontend

A React + Vite + TypeScript frontend for the S&P 500 financial heatmap dashboard.

## Features

- **Heatmap Visualization**: Treemap-style visualization of S&P 500 companies by sector
- **Sector Navigation**: Tab-based navigation across all S&P 500 sectors
- **Company Details**: Click any tile to view detailed company information in a side drawer
- **Search**: Search companies by symbol, name, or sub-industry
- **Dark Mode**: Toggle between light and dark themes
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Updates**: Refresh button to fetch latest data

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **TailwindCSS** - Styling
- **Framer Motion** - Animations
- **@nivo/treemap** - Heatmap visualization
- **Lucide React** - Icons

## Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

The app will be available at `http://localhost:3000`

### Environment Variables

Create a `.env` file in the `frontend` directory (optional):

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

If not set, it defaults to `http://127.0.0.1:8001`.

### Build for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

## Project Structure

```
frontend/
├── src/
│   ├── components/       # React components
│   │   ├── Header.tsx
│   │   ├── SectorTabs.tsx
│   │   ├── HeatmapTreemap.tsx
│   │   ├── CompanyDrawer.tsx
│   │   ├── SearchBar.tsx
│   │   ├── ThemeToggle.tsx
│   │   ├── HeatmapLegend.tsx
│   │   ├── Skeleton.tsx
│   │   └── ErrorToast.tsx
│   ├── lib/              # Utilities and API client
│   │   ├── api.ts
│   │   └── format.ts
│   ├── App.tsx           # Main app component
│   ├── main.tsx          # Entry point
│   └── styles.css        # Global styles
├── index.html
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

## API Integration

The frontend expects a backend API running at `http://127.0.0.1:8001` with the following endpoints:

- `GET /health` - Health check
- `GET /api/index` - S&P 500 index data
- `GET /api/sectors` - List of sectors
- `GET /api/sector/{sector}?limit=80` - Companies in a sector
- `GET /api/subsectors/{sector}` - Sub-industries in a sector
- `GET /api/subsector/{sector}/{subIndustry}?limit=80` - Companies in a sub-industry
- `GET /api/search?q=...` - Search companies

## Design Philosophy

The UI follows a clean, minimal "Apple-like" aesthetic:
- Large whitespace
- Soft borders and subtle shadows
- Smooth transitions
- Modern typography
- Dark mode as default

## License

MIT
