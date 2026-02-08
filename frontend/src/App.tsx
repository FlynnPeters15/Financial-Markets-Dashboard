import { useState, useEffect, useCallback, useMemo } from 'react';
import { Header } from './components/Header';
import { SectorTabs } from './components/SectorTabs';
import { HeatmapTreemap } from './components/HeatmapTreemap';
import { HeatmapLegend } from './components/HeatmapLegend';
import { CompanyDrawer } from './components/CompanyDrawer';
import { Skeleton, HeatmapSkeleton } from './components/Skeleton';
import { ErrorToast } from './components/ErrorToast';
import { apiClient, CompanyQuote, SectorResponse, IndexResponse } from './lib/api';
import { Sector, SECTORS, formatPercent, formatCurrency } from './lib/format';
import { RefreshCw } from 'lucide-react';
import { motion } from 'framer-motion';

function App() {
  const [activeSector, setActiveSector] = useState<Sector>('All');
  const [companies, setCompanies] = useState<CompanyQuote[]>([]);
  const [indexData, setIndexData] = useState<IndexResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<CompanyQuote | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Cache for sector data
  const [sectorCache, setSectorCache] = useState<Map<string, SectorResponse>>(new Map());

  const fetchSectorData = useCallback(async (sector: Sector, refresh = false) => {
    if (sector === 'All') {
      // For "All", fetch index data
      setLoading(true);
      setError(null);
      try {
        const index = await apiClient.getIndex();
        setIndexData(index);
        setCompanies([]);
        setLastUpdated(new Date(index.ts));
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch index data';
        setError(message);
        setIndexData(null);
      } finally {
        setLoading(false);
      }
      return;
    }

    // Check cache first (unless refresh)
    if (!refresh && sectorCache.has(sector)) {
      const cached = sectorCache.get(sector)!;
      setCompanies(cached.companies);
      setLastUpdated(new Date(cached.updated_at));
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.getSector(sector, 80, refresh);
      setCompanies(response.companies);
      setLastUpdated(new Date(response.updated_at));
      
      // Update cache
      setSectorCache((prev) => {
        const next = new Map(prev);
        next.set(sector, response);
        return next;
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch data';
      setError(message);
      
      // If we have cached data, use it
      if (sectorCache.has(sector)) {
        const cached = sectorCache.get(sector)!;
        setCompanies(cached.companies);
        setLastUpdated(new Date(cached.updated_at));
      } else {
        setCompanies([]);
      }
    } finally {
      setLoading(false);
    }
  }, [sectorCache]);

  useEffect(() => {
    fetchSectorData(activeSector);
  }, [activeSector]);

  const handleRefresh = useCallback(() => {
    fetchSectorData(activeSector, true);
  }, [activeSector, fetchSectorData]);

  const handleSectorChange = useCallback((sector: Sector) => {
    setActiveSector(sector);
    setSearchQuery(''); // Clear search when switching sectors
  }, []);

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  const handleCompanyClick = useCallback((company: CompanyQuote) => {
    setSelectedCompany(company);
    setDrawerOpen(true);
  }, []);

  // Filter companies based on search
  const filteredCompanies = useMemo(() => {
    if (!searchQuery.trim()) {
      return companies;
    }
    const query = searchQuery.toLowerCase();
    return companies.filter(
      (c) =>
        c.symbol.toLowerCase().includes(query) ||
        c.name.toLowerCase().includes(query) ||
        c.subIndustry.toLowerCase().includes(query)
    );
  }, [companies, searchQuery]);

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <Header onSearch={handleSearch} />
      <SectorTabs activeSector={activeSector} onSectorChange={handleSectorChange} />

      <main className="container mx-auto px-4 py-6">
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-2xl font-semibold mb-1">
                {activeSector === 'All' ? 'S&P 500 Overview' : activeSector}
              </h2>
              {lastUpdated && (
                <p className="text-sm text-muted-foreground">
                  Last updated: {lastUpdated.toLocaleTimeString()}
                </p>
              )}
            </div>
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-card border border-border rounded-lg hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {error && (
          <ErrorToast
            message={error}
            onDismiss={() => setError(null)}
            type={error.includes('429') ? 'warning' : 'error'}
          />
        )}

        {activeSector === 'All' && companies.length === 0 && !loading ? (
          <div className="space-y-6">
            {indexData ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-8 bg-card border border-border rounded-lg shadow-sm"
              >
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h3 className="text-2xl font-semibold mb-1">{indexData.name}</h3>
                    <p className="text-muted-foreground">{indexData.symbol}</p>
                  </div>
                  <div className="text-right">
                    <div className={`text-3xl font-bold ${indexData.pctChange >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {formatPercent(indexData.pctChange)}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {formatCurrency(indexData.change)} change
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <div className="text-sm text-muted-foreground mb-1">Close</div>
                    <div className="text-lg font-semibold">{formatCurrency(indexData.close)}</div>
                  </div>
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <div className="text-sm text-muted-foreground mb-1">Previous Close</div>
                    <div className="text-lg font-semibold">{formatCurrency(indexData.prevClose)}</div>
                  </div>
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <div className="text-sm text-muted-foreground mb-1">Source</div>
                    <div className="text-lg font-semibold capitalize">{indexData.source.replace('_', ' ')}</div>
                  </div>
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <div className="text-sm text-muted-foreground mb-1">Updated</div>
                    <div className="text-lg font-semibold">{new Date(indexData.ts).toLocaleTimeString()}</div>
                  </div>
                </div>
              </motion.div>
            ) : null}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="p-12 text-center bg-card border border-border rounded-lg"
            >
              <h3 className="text-xl font-semibold mb-2">Select a sector to view heatmap</h3>
              <p className="text-muted-foreground">
                Choose a sector from the tabs above to see the company heatmap
              </p>
            </motion.div>
          </div>
        ) : (
          <>
            {loading ? (
              <HeatmapSkeleton />
            ) : (
              <div className="bg-card border border-border rounded-lg p-6 shadow-sm">
                <HeatmapTreemap
                  data={filteredCompanies}
                  onNodeClick={handleCompanyClick}
                />
              </div>
            )}

            <div className="mt-6">
              <HeatmapLegend />
            </div>

            {searchQuery && (
              <div className="mt-4 text-sm text-muted-foreground">
                Showing {filteredCompanies.length} of {companies.length} companies
              </div>
            )}
          </>
        )}

        <footer className="mt-12 py-6 text-center text-sm text-muted-foreground border-t border-border">
          <p>Data: Finnhub (free tier) • Cached</p>
        </footer>
      </main>

      <CompanyDrawer
        company={selectedCompany}
        isOpen={drawerOpen}
        onClose={handleCloseDrawer}
      />
    </div>
  );
}

export default App;
