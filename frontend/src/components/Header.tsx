import { SearchBar } from './SearchBar';
import { ThemeToggle } from './ThemeToggle';

interface HeaderProps {
  onSearch: (query: string) => void;
}

export function Header({ onSearch }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4 flex-1 min-w-0">
            <h1 className="text-xl font-semibold whitespace-nowrap">S&P 500 Heatmap</h1>
            <div className="hidden md:flex flex-1 max-w-md">
              <SearchBar onSearch={onSearch} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="md:hidden">
              <SearchBar onSearch={onSearch} />
            </div>
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>
  );
}
