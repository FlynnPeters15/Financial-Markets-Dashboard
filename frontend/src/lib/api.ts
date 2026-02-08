// Use relative paths when in dev (Vite proxy) or absolute URL in production
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

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
  marketCap?: number | null;
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
    public statusText: string,
    public responseBody?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

class ApiClient {
  private baseURL: string;
  private abortControllers: Map<string, AbortController> = new Map();

  constructor(baseURL: string) {
    // Use relative paths if baseURL is empty (dev mode with proxy)
    this.baseURL = baseURL ? baseURL.replace(/\/$/, '') : '';
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    // Use relative path if baseURL is empty (dev mode with Vite proxy)
    const url = this.baseURL ? `${this.baseURL}${endpoint}` : endpoint;
    const controller = new AbortController();
    const key = `${options.method || 'GET'}:${endpoint}`;
    
    // Cancel previous request for same endpoint
    const prevController = this.abortControllers.get(key);
    if (prevController) {
      prevController.abort();
    }
    this.abortControllers.set(key, controller);

    const isDev = import.meta.env.DEV;

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      // Log request details in dev mode
      if (isDev) {
        console.log(`[API] ${options.method || 'GET'} ${endpoint}`, {
          status: response.status,
          statusText: response.statusText,
        });
      }

      if (!response.ok) {
        // Try to parse error response as JSON, fallback to text
        let errorBody: any = null;
        const contentType = response.headers.get('content-type');
        
        try {
          if (contentType && contentType.includes('application/json')) {
            errorBody = await response.json();
          } else {
            errorBody = await response.text();
          }
        } catch (parseError) {
          // If parsing fails, use status text
          errorBody = response.statusText;
        }

        // Log error details in dev mode
        if (isDev) {
          console.error(`[API Error] ${options.method || 'GET'} ${endpoint}`, {
            status: response.status,
            statusText: response.statusText,
            body: errorBody,
          });
        }

        // Create user-friendly error message
        let errorMessage = `API request failed: ${response.statusText}`;
        if (response.status === 429) {
          errorMessage = 'Rate limit exceeded. Please try again later.';
          if (errorBody && typeof errorBody === 'object' && errorBody.detail?.message) {
            errorMessage = errorBody.detail.message;
          }
        } else if (errorBody) {
          if (typeof errorBody === 'object' && errorBody.detail) {
            if (typeof errorBody.detail === 'string') {
              errorMessage = errorBody.detail;
            } else if (errorBody.detail.reason) {
              errorMessage = errorBody.detail.reason;
            } else if (errorBody.detail.message) {
              errorMessage = errorBody.detail.message;
            }
          } else if (typeof errorBody === 'string') {
            errorMessage = errorBody;
          }
        }

        throw new ApiError(
          errorMessage,
          response.status,
          response.statusText,
          errorBody
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
      
      // Network errors
      const networkMessage = error instanceof Error ? error.message : 'Unknown error';
      if (isDev) {
        console.error(`[API Network Error] ${options.method || 'GET'} ${endpoint}`, error);
      }
      throw new Error(`Network error: ${networkMessage}`);
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
