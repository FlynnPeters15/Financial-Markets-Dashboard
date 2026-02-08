export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  return `$${value.toFixed(2)}`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  return value.toFixed(2);
}

export function getColorForPercentChange(
  pctChange: number | null | undefined,
  status: string
): string {
  if (status !== 'ok' || pctChange === null || pctChange === undefined || isNaN(pctChange)) {
    return '#6b7280'; // gray
  }

  // Clamp to [-5, +5] for color mapping
  const clamped = Math.max(-5, Math.min(5, pctChange));
  
  // Map to 0-1 range
  const normalized = (clamped + 5) / 10;
  
  // Diverging color scale: red (0) -> gray (0.5) -> green (1)
  if (normalized < 0.5) {
    // Red to gray
    const t = normalized * 2;
    const r = Math.round(220 + (100 - 220) * t);
    const g = Math.round(38 + (100 - 38) * t);
    const b = Math.round(38 + (100 - 38) * t);
    return `rgb(${r}, ${g}, ${b})`;
  } else {
    // Gray to green
    const t = (normalized - 0.5) * 2;
    const r = Math.round(100 + (34 - 100) * t);
    const g = Math.round(100 + (197 - 100) * t);
    const b = Math.round(100 + (94 - 100) * t);
    return `rgb(${r}, ${g}, ${b})`;
  }
}

export function getTextColorForPercentChange(
  pctChange: number | null | undefined,
  status: string
): string {
  if (status !== 'ok' || pctChange === null || pctChange === undefined || isNaN(pctChange)) {
    return '#9ca3af'; // muted gray
  }
  return pctChange >= 0 ? '#22c55e' : '#ef4444';
}

export const SECTORS = [
  'All',
  'Communication Services',
  'Consumer Discretionary',
  'Consumer Staples',
  'Energy',
  'Financials',
  'Health Care',
  'Industrials',
  'Information Technology',
  'Materials',
  'Real Estate',
  'Utilities',
] as const;

export type Sector = typeof SECTORS[number];
