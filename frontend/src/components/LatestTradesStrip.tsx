import type { TradeItem } from "../types/trade";
import { formatINR, formatInteger, formatTimestampIST } from "../utils/format";

interface LatestTradesStripProps {
  trades: TradeItem[];
  isLoading: boolean;
}

export function LatestTradesStrip({ trades, isLoading }: LatestTradesStripProps) {
  return (
    <section className="card" aria-label="Latest executed trade records">
      <div className="card-header">
        <div className="card-title-group">
          <h2 className="card-title">Latest Trade Records</h2>
          <p className="card-subtitle">
            Most recent simulated executions ordered by exchange timestamp
          </p>
        </div>
        <span className="badge badge-neutral tabular-nums">
          Latest {trades.length || 5}
        </span>
      </div>

      {isLoading && trades.length === 0 ? (
        <div className="state-box state-box-compact">
          <p className="state-desc">Loading latest trade records...</p>
        </div>
      ) : trades.length === 0 ? (
        <div className="state-box state-box-compact">
          <p className="state-desc">No trade records available.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table data-table-compact">
            <thead>
              <tr>
                <th>Trade ID</th>
                <th>Timestamp (IST)</th>
                <th>Symbol</th>
                <th>Client</th>
                <th className="th-right">Quantity</th>
                <th className="th-right">Price (INR)</th>
                <th className="th-right">Trade Value</th>
                <th>Origin</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => (
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
                        trade.source === "BSE_PULL" ? "badge-info" : "badge-neutral"
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
    </section>
  );
}
