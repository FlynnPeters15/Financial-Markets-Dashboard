const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001';

export interface CompanyQuote {
  symbol: string;
  name: string;
  subIndustry: string;
  close: number | null;
  prevClose: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  change: number | null;
  pctChange: number | null;
  status: string;
  error?: string | null;
  source: string;
}

export interface SectorMeta {
  requested: number;
  returned: number;
  cache_hits: number;
  api_calls: number;
  rate_limited: boolean;
}

export interface SectorResponse {
  sector: string;
  updated_at: string;
  companies: CompanyQuote[];
  meta: SectorMeta;
}

export interface SectorSummary {
  sector: string;
  count: number;
  subIndustryCount: number;
}

export interface IndexResponse {
  symbol: string;
  name: string;
  close: number;
  prevClose: number;
  change: number;
  pctChange: number;
  ts: string;
  source: string;
}

export interface SearchResult {
  symbol: string;
  name: string;
  sector: string;
  subIndustry: string;
}

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public statusText: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

class ApiClient {
  private baseURL: string;
  private abortControllers: Map<string, AbortController> = new Map();

  constructor(baseURL: string) {
    this.baseURL = baseURL.replace(/\/$/, '');
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const controller = new AbortController();
    const key = `${options.method || 'GET'}:${endpoint}`;
    
    // Cancel previous request for same endpoint
    const prevController = this.abortControllers.get(key);
    if (prevController) {
      prevController.abort();
    }
    this.abortControllers.set(key, controller);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        throw new ApiError(
          `API request failed: ${response.statusText}`,
          response.status,
          response.statusText
        );
      }

      const data = await response.json();
      this.abortControllers.delete(key);
      return data as T;
    } catch (error) {
      this.abortControllers.delete(key);
      if (error instanceof ApiError) {
        throw error;
      }
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Request aborted');
      }
      throw new Error(`Network error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async health(): Promise<{ ok: boolean; ts: string; version: string }> {
    return this.request('/health');
  }

  async getIndex(): Promise<IndexResponse> {
    return this.request('/api/index');
  }

  async getSectors(): Promise<SectorSummary[]> {
    return this.request('/api/sectors');
  }

  async getSector(sector: string, limit = 80, refresh = false): Promise<SectorResponse> {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (refresh) {
      params.append('refresh', 'true');
    }
    const encodedSector = encodeURIComponent(sector);
    return this.request(`/api/sector/${encodedSector}?${params.toString()}`);
  }

  async getSubsectors(sector: string): Promise<{ subIndustry: string; count: number }[]> {
    const encodedSector = encodeURIComponent(sector);
    return this.request(`/api/subsectors/${encodedSector}`);
  }

  async getSubsector(
    sector: string,
    subIndustry: string,
    limit = 80
  ): Promise<SectorResponse> {
    const encodedSector = encodeURIComponent(sector);
    const encodedSubIndustry = encodeURIComponent(subIndustry);
    return this.request(`/api/subsector/${encodedSector}/${encodedSubIndustry}?limit=${limit}`);
  }

  async search(query: string): Promise<SearchResult[]> {
    return this.request(`/api/search?q=${encodeURIComponent(query)}`);
  }
}

export const apiClient = new ApiClient(API_BASE_URL);
