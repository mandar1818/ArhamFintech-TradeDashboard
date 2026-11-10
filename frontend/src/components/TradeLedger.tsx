import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Search,
} from "lucide-react";
import type {
  SortOrder,
  TradeFiltersResponse,
  TradeQueryParams,
  TradesResponse,
  TradeSortField,
} from "../types/trade";
import { formatINR, formatInteger, formatTimestampIST } from "../utils/format";

interface TradeLedgerProps {
  data: TradesResponse | null;
  filters: TradeFiltersResponse;
  query: TradeQueryParams;
  searchInput: string;
  isLoading: boolean;
  error: string | null;
  onSearchInputChange: (value: string) => void;
  onSymbolChange: (symbol: string) => void;
  onClientChange: (client: string) => void;
  onSortChange: (field: TradeSortField) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onResetFilters: () => void;
  onRetryFetch: () => void;
}

const COLUMNS: Array<{
  key: TradeSortField;
  label: string;
  align?: "right";
}> = [
  { key: "trade_id", label: "Trade ID" },
  { key: "timestamp", label: "Timestamp (IST)" },
  { key: "symbol", label: "Symbol" },
  { key: "client", label: "Client" },
  { key: "quantity", label: "Quantity", align: "right" },
  { key: "price", label: "Price (INR)", align: "right" },
  { key: "value", label: "Trade Value", align: "right" },
];

export function TradeLedger({
  data,
  filters,
  query,
  searchInput,
  isLoading,
  error,
  onSearchInputChange,
  onSymbolChange,
  onClientChange,
  onSortChange,
  onPageChange,
  onPageSizeChange,
  onResetFilters,
  onRetryFetch,
}: TradeLedgerProps) {
  const hasActiveFilters = Boolean(
    searchInput.trim() || query.symbol || query.client
  );

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const page = data?.page ?? query.page;
  const pageSize = data?.page_size ?? query.page_size;
  const totalPages = data?.total_pages ?? 0;
  const startRecord = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endRecord = Math.min(page * pageSize, total);

  const renderSortIcon = (field: TradeSortField) => {
    if (query.sort_by !== field) {
      return <ArrowUpDown size={12} opacity={0.5} />;
    }
    return query.sort_order === "asc" ? (
      <ArrowUp size={12} />
    ) : (
      <ArrowDown size={12} />
    );
  };

  return (
    <section className="card" aria-label="BSE trade ledger">
      <div className="card-header">
        <div className="card-title-group">
          <h2 className="card-title">Trade Ledger</h2>
          <p className="card-subtitle tabular-nums">
            {data
              ? hasActiveFilters
                ? `${formatInteger(total)} matching trades of ${formatInteger(data.summary.total_trades)} total`
                : `${formatInteger(total)} total records`
              : "Loading trade ledger..."}
          </p>
        </div>

        {data && hasActiveFilters && (
          <div className="meta-pill tabular-nums">
            Filtered Qty: {formatInteger(data.filtered_summary.total_quantity)} ·
            Filtered Value: {formatINR(data.filtered_summary.total_value)}
          </div>
        )}
      </div>

      <div className="toolbar">
        <div className="search-box">
          <Search size={14} className="search-icon" />
          <input
            type="search"
            className="input search-input"
            placeholder="Search by trade ID, stock symbol, or client..."
            value={searchInput}
            onChange={(e) => onSearchInputChange(e.target.value)}
            aria-label="Search trades"
          />
        </div>

        <select
          className="select filter-select"
          value={query.symbol ?? ""}
          onChange={(e) => onSymbolChange(e.target.value)}
          aria-label="Filter by symbol"
        >
          <option value="">All Symbols ({filters.symbols.length})</option>
          {filters.symbols.map((sym) => (
            <option key={sym} value={sym}>
              {sym}
            </option>
          ))}
        </select>

        <select
          className="select filter-select"
          value={query.client ?? ""}
          onChange={(e) => onClientChange(e.target.value)}
          aria-label="Filter by client"
        >
          <option value="">All Clients ({filters.clients.length})</option>
          {filters.clients.map((cli) => (
            <option key={cli} value={cli}>
              {cli}
            </option>
          ))}
        </select>

        {hasActiveFilters && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onResetFilters}
          >
            <RotateCcw size={12} />
            <span>Reset</span>
          </button>
        )}
      </div>

      {error ? (
        <div className="state-box">
          <h3 className="state-title">Failed to Load Trade Records</h3>
          <p className="state-desc">{error}</p>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onRetryFetch}
          >
            Retry Query
          </button>
        </div>
      ) : isLoading && items.length === 0 ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    className={col.align === "right" ? "th-right" : ""}
                  >
                    {col.label}
                  </th>
                ))}
                <th>Origin</th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 6 }).map((_, idx) => (
                <tr key={idx}>
                  <td colSpan={8}>
                    <div className="skeleton-row" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : items.length === 0 ? (
        <div className="state-box">
          <h3 className="state-title">No Matching Trades Found</h3>
          <p className="state-desc">
            No trades match your current search term or symbol/client filters.
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onResetFilters}
            >
              Clear Active Filters
            </button>
          )}
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                {COLUMNS.map((col) => {
                  const isActive = query.sort_by === col.key;
                  const nextDir: SortOrder =
                    isActive && query.sort_order === "desc" ? "asc" : "desc";
                  return (
                    <th
                      key={col.key}
                      className={col.align === "right" ? "th-right" : ""}
                    >
                      <button
                        type="button"
                        className={`sort-btn ${isActive ? "active" : ""}`}
                        onClick={() => onSortChange(col.key)}
                        title={`Sort by ${col.label} (${nextDir})`}
                      >
                        <span>{col.label}</span>
                        {renderSortIcon(col.key)}
                      </button>
                    </th>
                  );
                })}
                <th>Origin</th>
              </tr>
            </thead>
            <tbody className={isLoading ? "tbody-loading" : ""}>
              {items.map((trade) => (
                <tr key={trade.trade_id}>
                  <td className="mono">{trade.trade_id}</td>
                  <td className="tabular-nums">
                    {formatTimestampIST(trade.timestamp)}
                  </td>
                  <td>
                    <span className="symbol-tag">{trade.symbol}</span>
                  </td>
                  <td>{trade.client}</td>
                  <td className="td-right tabular-nums">
                    {formatInteger(trade.quantity)}
                  </td>
                  <td className="td-right tabular-nums">
                    {formatINR(trade.price)}
                  </td>
                  <td className="td-right tabular-nums font-semibold">
                    {formatINR(trade.trade_value)}
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        trade.source === "BSE_PULL"
                          ? "badge-info"
                          : "badge-neutral"
                      }`}
                    >
                      {trade.source === "BSE_PULL" ? "BSE PULL" : "SEED"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="pagination-bar">
        <div className="pagination-info tabular-nums">
          {total > 0
            ? `Showing ${formatInteger(startRecord)}–${formatInteger(endRecord)} of ${formatInteger(total)} trades`
            : "Showing 0 trades"}
        </div>

        <div className="pagination-controls">
          <label htmlFor="page-size-select" className="pagination-label">
            Rows:
          </label>
          <select
            id="page-size-select"
            className="select select-compact"
            value={query.page_size}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
          >
            {[10, 25, 50, 100].map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>

          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={page <= 1 || isLoading}
            onClick={() => onPageChange(page - 1)}
            aria-label="Previous page"
          >
            <ChevronLeft size={14} />
            <span>Prev</span>
          </button>

          <span className="pagination-info pagination-page-label tabular-nums">
            Page {totalPages === 0 ? 0 : page} / {totalPages}
          </span>

          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={totalPages === 0 || page >= totalPages || isLoading}
            onClick={() => onPageChange(page + 1)}
            aria-label="Next page"
          >
            <span>Next</span>
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </section>
  );
}
