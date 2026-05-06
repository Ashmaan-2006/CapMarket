const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type Ticker = {
  id: number;
  symbol: string;
  name: string | null;
  asset_type: string;
  exchange: string | null;
  currency: string;
  is_active: boolean;
};

export type PricePoint = {
  price_date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  adjusted_close: string | null;
  volume: number;
};

export type MetricPoint = {
  metric_date: string;
  daily_return: string | null;
  weekly_return: string | null;
  monthly_return: string | null;
  volatility_20d: string | null;
  sma_20: string | null;
  sma_50: string | null;
  ema_20: string | null;
  drawdown: string | null;
  volume_ratio_20d: string | null;
};

export type EtlJob = {
  id: number;
  job_type: string;
  status: string;
  symbols: string[];
  started_at: string | null;
  finished_at: string | null;
  rows_extracted: number;
  rows_loaded: number;
  error_message: string | null;
};

export type AiReport = {
  id: number;
  symbol: string;
  report_date: string;
  report_type: string;
  summary: string;
  trend_insights: string[];
  anomaly_explanations: string[];
  risk_notes: string[];
  metrics_snapshot: Record<string, unknown>;
  model: string;
  created_at: string;
};

type PaginatedResponse<T> = {
  items: T[];
  limit: number;
  offset: number;
  count: number;
};

type SymbolSeriesResponse<T> = PaginatedResponse<T> & {
  symbol: string;
  start_date?: string | null;
  end_date?: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  tickers: async () => {
    const response = await request<PaginatedResponse<Ticker>>("/tickers");
    return response.items;
  },
  prices: async (symbol: string) => {
    const response = await request<SymbolSeriesResponse<PricePoint>>(
      `/market-data/${symbol}?limit=252`
    );
    return response.items;
  },
  metrics: async (symbol: string) => {
    const response = await request<SymbolSeriesResponse<MetricPoint>>(
      `/metrics/${symbol}?limit=252`
    );
    return response.items;
  },
  etlStatus: () => request<EtlJob[]>("/etl/status"),
  runEtl: (symbols: string[]) =>
    request<EtlJob>("/etl/run", { method: "POST", body: JSON.stringify({ symbols }) }),
  reports: (symbol: string) => request<AiReport[]>(`/reports/${symbol}`),
  generateReport: (symbol: string) =>
    request<AiReport>("/reports/generate", {
      method: "POST",
      body: JSON.stringify({ symbol, report_type: "daily" })
    })
};
