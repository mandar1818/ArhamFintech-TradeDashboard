import { Activity, IndianRupee, Layers, Users } from "lucide-react";
import type { TradeSummary } from "../types/trade";
import { formatINR, formatINRCompact, formatInteger } from "../utils/format";

interface KpiGridProps {
  summary: TradeSummary | null;
  isLoading: boolean;
}

export function KpiGrid({ summary, isLoading }: KpiGridProps) {
  const placeholder = isLoading && !summary ? "—" : "0";

  return (
    <section className="kpi-grid" aria-label="Ledger summary metrics">
      <article className="kpi-card">
        <div className="kpi-header">
          <span>Total Trades</span>
          <Activity size={15} />
        </div>
        <div className="kpi-value tabular-nums">
          {summary ? formatInteger(summary.total_trades) : placeholder}
        </div>
        <div className="kpi-caption">Recorded executions in ledger</div>
      </article>

      <article className="kpi-card">
        <div className="kpi-header">
          <span>Total Traded Quantity</span>
          <Layers size={15} />
        </div>
        <div className="kpi-value tabular-nums">
          {summary ? formatInteger(summary.total_quantity) : placeholder}
        </div>
        <div className="kpi-caption">Total shares across all trades</div>
      </article>

      <article className="kpi-card">
        <div className="kpi-header">
          <span>Total Trade Value</span>
          <IndianRupee size={15} />
        </div>
        <div
          className="kpi-value tabular-nums"
          title={summary ? formatINR(summary.total_value) : undefined}
        >
          {summary ? formatINRCompact(summary.total_value) : placeholder}
        </div>
        <div className="kpi-caption tabular-nums">
          {summary ? formatINR(summary.total_value) : "Awaiting ledger total"}
        </div>
      </article>

      <article className="kpi-card">
        <div className="kpi-header">
          <span>Unique Clients</span>
          <Users size={15} />
        </div>
        <div className="kpi-value tabular-nums">
          {summary ? formatInteger(summary.unique_clients) : placeholder}
        </div>
        <div className="kpi-caption">Distinct client accounts</div>
      </article>
    </section>
  );
}
