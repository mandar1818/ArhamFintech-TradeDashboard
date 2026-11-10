import type {
  IngestionHistoryResponse,
  PullTradesResponse,
  TradeFiltersResponse,
  TradeQueryParams,
  TradesResponse,
} from "../types/trade";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  public readonly status: number;
  public readonly code: string;
  public readonly activeJobId?: string;

  constructor(
    message: string,
    status: number,
    code = "api_error",
    activeJobId?: string
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.activeJobId = activeJobId;
  }
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let data: Record<string, unknown> = {};
  if (text) {
    try {
      data = JSON.parse(text) as Record<string, unknown>;
    } catch {
      throw new ApiError(
        `Unexpected response format (HTTP ${response.status})`,
        response.status,
        "invalid_json"
      );
    }
  }

  if (!response.ok) {
    const message =
      typeof data.message === "string"
        ? data.message
        : `Request failed with status ${response.status}`;
    const code = typeof data.error === "string" ? data.error : "http_error";
    const activeJobId =
      typeof data.active_job_id === "string" ? data.active_job_id : undefined;
    throw new ApiError(message, response.status, code, activeJobId);
  }

  return data as T;
}

export async function fetchTrades(
  params: TradeQueryParams,
  signal?: AbortSignal
): Promise<TradesResponse> {
  const url = new URL(`${API_BASE_URL}/getTrades`);
  url.searchParams.set("page", String(params.page));
  url.searchParams.set("page_size", String(params.page_size));
  url.searchParams.set("sort_by", params.sort_by);
  url.searchParams.set("sort_order", params.sort_order);

  if (params.search && params.search.trim()) {
    url.searchParams.set("search", params.search.trim());
  }
  if (params.symbol && params.symbol.trim()) {
    url.searchParams.set("symbol", params.symbol.trim());
  }
  if (params.client && params.client.trim()) {
    url.searchParams.set("client", params.client.trim());
  }

  const response = await fetch(url.toString(), { signal });
  return parseJsonResponse<TradesResponse>(response);
}

export async function fetchLatestTrades(
  limit = 5,
  signal?: AbortSignal
): Promise<TradesResponse> {
  return fetchTrades(
    {
      page: 1,
      page_size: limit,
      sort_by: "timestamp",
      sort_order: "desc",
    },
    signal
  );
}

export async function fetchTradeFilters(
  signal?: AbortSignal
): Promise<TradeFiltersResponse> {
  const response = await fetch(`${API_BASE_URL}/trades/filters`, { signal });
  return parseJsonResponse<TradeFiltersResponse>(response);
}

export async function fetchIngestionJobs(
  limit = 20,
  signal?: AbortSignal
): Promise<IngestionHistoryResponse> {
  const url = new URL(`${API_BASE_URL}/jobs`);
  url.searchParams.set("limit", String(limit));
  const response = await fetch(url.toString(), { signal });
  return parseJsonResponse<IngestionHistoryResponse>(response);
}

export async function triggerPullTrades(): Promise<PullTradesResponse> {
  const response = await fetch(`${API_BASE_URL}/pull-trades`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });
  return parseJsonResponse<PullTradesResponse>(response);
}
