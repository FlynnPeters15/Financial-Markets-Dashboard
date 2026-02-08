import { SECTORS, Sector } from '../lib/format';
import { motion } from 'framer-motion';

interface SectorTabsProps {
  activeSector: Sector;
  onSectorChange: (sector: Sector) => void;
}

export function SectorTabs({ activeSector, onSectorChange }: SectorTabsProps) {
  return (
    <div className="sticky top-[73px] z-30 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 py-3">
        <div className="overflow-x-auto scrollbar-hide">
          <div className="flex gap-2 min-w-max">
            {SECTORS.map((sector) => (
              <button
                key={sector}
                onClick={() => onSectorChange(sector)}
                className={`relative px-4 py-2 rounded-full text-sm font-medium transition-colors whitespace-nowrap ${
                  activeSector === sector
                    ? 'text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                aria-pressed={activeSector === sector}
              >
                {activeSector === sector && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute inset-0 bg-card border border-border rounded-full"
                    transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }}
                  />
                )}
                <span className="relative z-10">{sector}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
