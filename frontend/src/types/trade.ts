export type TradeSortField =
  | "timestamp"
  | "trade_id"
  | "client"
  | "symbol"
  | "quantity"
  | "price"
  | "value";

export type SortOrder = "asc" | "desc";

export interface TradeItem {
  trade_id: string;
  client: string;
  symbol: string;
  quantity: number;
  price: number;
  trade_value: number;
  timestamp: string;
  source: string;
}

export interface TradeSummary {
  total_trades: number;
  total_quantity: number;
  total_value: number;
  unique_clients: number;
  latest_trade_at: string | null;
}

export interface TradesResponse {
  items: TradeItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  summary: TradeSummary;
  filtered_summary: TradeSummary;
}

export interface TradeFiltersResponse {
  symbols: string[];
  clients: string[];
}

export interface TradeQueryParams {
  page: number;
  page_size: number;
  search?: string;
  symbol?: string;
  client?: string;
  sort_by: TradeSortField;
  sort_order: SortOrder;
}

export type JobStatus = "PENDING" | "RUNNING" | "RETRYING" | "COMPLETED" | "FAILED";

export interface IngestionJob {
  job_id: string;
  status: JobStatus;
  progress: number;
  stage: string;
  message: string;
  delay_seconds: number;
  batch_size: number;
  records_fetched: number;
  records_inserted: number;
  duplicates_skipped: number;
  attempt_count: number;
  max_retries: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
}

export interface IngestionHistoryResponse {
  active_job: IngestionJob | null;
  last_successful_sync: string | null;
  jobs: IngestionJob[];
  total: number;
}

export interface PullTradesResponse {
  job_id: string;
  status: JobStatus;
  message: string;
  estimated_delay_seconds: number;
  batch_size: number;
  max_retries: number;
  created_at: string;
}

export type SSEConnectionStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected";

export interface SSEConnectedSnapshot {
  active_job: IngestionJob | null;
  latest_job: IngestionJob | null;
  last_successful_sync: string | null;
  server_time: string;
}
