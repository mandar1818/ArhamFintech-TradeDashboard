import { Clock, RefreshCw, Wifi, WifiOff } from "lucide-react";
import type { SSEConnectionStatus } from "../types/trade";
import { formatTimestampIST } from "../utils/format";

interface HeaderProps {
  connectionStatus: SSEConnectionStatus;
  lastSuccessfulSync: string | null;
  isIngestionActive: boolean;
  isPullSubmitting: boolean;
  onPullTrades: () => void;
}

const SSE_LABELS: Record<SSEConnectionStatus, string> = {
  connected: "SSE Connected",
  connecting: "SSE Connecting",
  reconnecting: "SSE Reconnecting",
  disconnected: "SSE Disconnected",
};

export function Header({
  connectionStatus,
  lastSuccessfulSync,
  isIngestionActive,
  isPullSubmitting,
  onPullTrades,
}: HeaderProps) {
  const isDisabled = isIngestionActive || isPullSubmitting;

  return (
    <header className="top-header">
      <div className="container header-inner">
        <div className="brand-group">
          <div className="brand-mark" aria-hidden="true">
            AF
          </div>
          <div>
            <h1 className="brand-title">Arham Fintech · BSE Trade Operations</h1>
            <p className="brand-subtitle">
              Simulated BSE Trade Ledger &amp; Asynchronous Ingestion Console
            </p>
          </div>
        </div>

        <div className="header-controls">
          <div
            className={`sse-pill ${connectionStatus}`}
            title="Real-time Server-Sent Events stream status"
          >
            {connectionStatus === "disconnected" ? (
              <WifiOff size={13} />
            ) : (
              <Wifi size={13} />
            )}
            <span className="status-dot" />
            <span>{SSE_LABELS[connectionStatus]}</span>
          </div>

          <div
            className="meta-pill tabular-nums"
            title="Timestamp of last completed BSE ingestion pull"
          >
            <Clock size={13} />
            <span>
              Last Sync:{" "}
              {lastSuccessfulSync
                ? formatTimestampIST(lastSuccessfulSync)
                : "No pull completed yet"}
            </span>
          </div>

          <button
            type="button"
            className="btn btn-primary"
            disabled={isDisabled}
            onClick={onPullTrades}
          >
            <RefreshCw size={14} className={isDisabled ? "spin" : ""} />
            <span>
              {isPullSubmitting
                ? "Queuing Pull..."
                : isIngestionActive
                  ? "Pull Running..."
                  : "Pull BSE Trades"}
            </span>
          </button>
        </div>
      </div>
    </header>
  );
}
