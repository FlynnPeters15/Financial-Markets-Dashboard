import { motion, AnimatePresence } from 'framer-motion';
import { X, ExternalLink } from 'lucide-react';
import { CompanyQuote } from '../lib/api';
import { formatPercent, formatCurrency, formatNumber } from '../lib/format';

interface CompanyDrawerProps {
  company: CompanyQuote | null;
  isOpen: boolean;
  onClose: () => void;
}

export function CompanyDrawer({ company, isOpen, onClose }: CompanyDrawerProps) {
  if (!company) return null;

  const handleExternalLink = () => {
    const url = `https://finviz.com/quote.ashx?t=${company.symbol}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50"
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-card border-l border-border shadow-xl z-50 overflow-y-auto"
          >
            <div className="p-6">
              <div className="flex items-start justify-between mb-6">
                <div className="flex-1">
                  <h2 className="text-2xl font-semibold mb-1">{company.name}</h2>
                  <p className="text-muted-foreground">{company.symbol}</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {company.subIndustry}
                  </p>
                </div>
                <button
                  onClick={onClose}
                  className="p-2 hover:bg-muted rounded-lg transition-colors"
                  aria-label="Close drawer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="mb-6">
                <div className="text-4xl font-bold mb-2">
                  {formatPercent(company.pctChange)}
                </div>
                <div className="text-lg text-muted-foreground">
                  {formatCurrency(company.change)} change
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="text-sm text-muted-foreground mb-1">Close</div>
                  <div className="text-lg font-semibold">
                    {formatCurrency(company.close)}
                  </div>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="text-sm text-muted-foreground mb-1">Previous Close</div>
                  <div className="text-lg font-semibold">
                    {formatCurrency(company.prevClose)}
                  </div>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="text-sm text-muted-foreground mb-1">Open</div>
                  <div className="text-lg font-semibold">
                    {formatCurrency(company.open)}
                  </div>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="text-sm text-muted-foreground mb-1">High</div>
                  <div className="text-lg font-semibold">
                    {formatCurrency(company.high)}
                  </div>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="text-sm text-muted-foreground mb-1">Low</div>
                  <div className="text-lg font-semibold">
                    {formatCurrency(company.low)}
                  </div>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="text-sm text-muted-foreground mb-1">Source</div>
                  <div className="text-lg font-semibold capitalize">
                    {company.source.replace('_', ' ')}
                  </div>
                </div>
              </div>

              {company.status !== 'ok' && company.error && (
                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg mb-6">
                  <div className="text-sm text-red-600 dark:text-red-400">
                    Error: {company.error}
                  </div>
                </div>
              )}

              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-3">Price Chart</h3>
                <div className="h-48 bg-muted/50 rounded-lg flex items-center justify-center">
                  <div className="text-muted-foreground text-sm">
                    Sparkline chart placeholder
                  </div>
                </div>
              </div>

              <button
                onClick={handleExternalLink}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-foreground text-background rounded-lg hover:opacity-90 transition-opacity"
              >
                <ExternalLink className="w-4 h-4" />
                View on Finviz
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
