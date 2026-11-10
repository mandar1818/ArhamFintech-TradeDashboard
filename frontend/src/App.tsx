import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  fetchIngestionJobs,
  fetchLatestTrades,
  fetchTradeFilters,
  fetchTrades,
  triggerPullTrades,
} from "./api/client";
import { Header } from "./components/Header";
import { IngestionHistory } from "./components/IngestionHistory";
import { IngestionStatusBanner } from "./components/IngestionStatusBanner";
import { KpiGrid } from "./components/KpiGrid";
import { LatestTradesStrip } from "./components/LatestTradesStrip";
import { TradeLedger } from "./components/TradeLedger";
import { useTradeEvents } from "./hooks/useTradeEvents";
import type {
  IngestionJob,
  SSEConnectedSnapshot,
  TradeFiltersResponse,
  TradeItem,
  TradeQueryParams,
  TradesResponse,
  TradeSortField,
} from "./types/trade";

const INITIAL_QUERY: TradeQueryParams = {
  page: 1,
  page_size: 25,
  search: "",
  symbol: "",
  client: "",
  sort_by: "timestamp",
  sort_order: "desc",
};

export default function App() {
  const [query, setQuery] = useState<TradeQueryParams>(INITIAL_QUERY);
  const [searchInput, setSearchInput] = useState("");
  const queryRef = useRef<TradeQueryParams>(query);
  queryRef.current = query;

  const [tradesData, setTradesData] = useState<TradesResponse | null>(null);
  const [isTradesLoading, setIsTradesLoading] = useState(true);
  const [tradesError, setTradesError] = useState<string | null>(null);

  const [latestTrades, setLatestTrades] = useState<TradeItem[]>([]);
  const [isLatestLoading, setIsLatestLoading] = useState(true);

  const [filters, setFilters] = useState<TradeFiltersResponse>({
    symbols: [],
    clients: [],
  });

  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [isJobsLoading, setIsJobsLoading] = useState(true);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [lastSuccessfulSync, setLastSuccessfulSync] = useState<string | null>(
    null
  );

  const [isPullSubmitting, setIsPullSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  const loadTrades = useCallback(async (params: TradeQueryParams, signal?: AbortSignal) => {
    setIsTradesLoading(true);
    setTradesError(null);
    try {
      const result = await fetchTrades(params, signal);
      setTradesData(result);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setTradesError(
        err instanceof Error ? err.message : "Failed to fetch trade records."
      );
    } finally {
      if (!signal?.aborted) {
        setIsTradesLoading(false);
      }
    }
  }, []);

  const loadAuxiliaryDashboardData = useCallback(async (signal?: AbortSignal) => {
    setIsLatestLoading(true);
    setIsJobsLoading(true);
    setJobsError(null);

    try {
      const [latestRes, filtersRes, jobsRes] = await Promise.all([
        fetchLatestTrades(5, signal),
        fetchTradeFilters(signal),
        fetchIngestionJobs(20, signal),
      ]);
      setLatestTrades(latestRes.items);
      setFilters(filtersRes);
      setJobs(jobsRes.jobs);
      setLastSuccessfulSync(jobsRes.last_successful_sync);
      return jobsRes;
    } catch (err) {
      if ((err as Error).name === "AbortError") return null;
      setJobsError(
        err instanceof Error
          ? err.message
          : "Unable to load ingestion synchronization state."
      );
      return null;
    } finally {
      if (!signal?.aborted) {
        setIsLatestLoading(false);
        setIsJobsLoading(false);
      }
    }
  }, []);

  const refreshJobsOnly = useCallback(async () => {
    try {
      const jobsRes = await fetchIngestionJobs(20);
      setJobs(jobsRes.jobs);
      setLastSuccessfulSync(jobsRes.last_successful_sync);
      setJobsError(null);
    } catch (err) {
      setJobsError(
        err instanceof Error ? err.message : "Failed to refresh job history."
      );
    }
  }, []);

  const handleIngestionCompleted = useCallback(
    (completedJob: IngestionJob) => {
      setActionError(null);
      setBannerDismissed(false);
      if (completedJob.completed_at) {
        setLastSuccessfulSync(completedJob.completed_at);
      }
      // Single automatic refresh upon SSE completion event (no polling).
      void loadTrades(queryRef.current);
      void loadAuxiliaryDashboardData();
    },
    [loadTrades, loadAuxiliaryDashboardData]
  );

  const handleIngestionFailed = useCallback(() => {
    setBannerDismissed(false);
    void refreshJobsOnly();
  }, [refreshJobsOnly]);

  const handleSnapshotSync = useCallback((snapshot: SSEConnectedSnapshot) => {
    if (snapshot.last_successful_sync) {
      setLastSuccessfulSync(snapshot.last_successful_sync);
    }
  }, []);

  const { connectionStatus, liveJob, setLiveJob } = useTradeEvents({
    onIngestionCompleted: handleIngestionCompleted,
    onIngestionFailed: handleIngestionFailed,
    onSnapshotSync: handleSnapshotSync,
  });

  // Un-dismiss status banner whenever a new job becomes active or changes job_id.
  const previousJobIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (liveJob && liveJob.job_id !== previousJobIdRef.current) {
      previousJobIdRef.current = liveJob.job_id;
      setBannerDismissed(false);
    }
  }, [liveJob]);

  // Initial mount fetch of auxiliary data (latest strip, filters, job history).
  useEffect(() => {
    const controller = new AbortController();
    void loadAuxiliaryDashboardData(controller.signal).then((jobsRes) => {
      if (jobsRes?.active_job) {
        setLiveJob((prev) => prev ?? jobsRes.active_job);
      }
    });
    return () => controller.abort();
  }, [loadAuxiliaryDashboardData, setLiveJob]);

  // Fetch trade table whenever query parameters change.
  useEffect(() => {
    const controller = new AbortController();
    void loadTrades(query, controller.signal);
    return () => controller.abort();
  }, [query, loadTrades]);

  // Debounce free-text search input before updating query.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery((prev) => {
        if ((prev.search ?? "") === searchInput) return prev;
        return { ...prev, search: searchInput, page: 1 };
      });
    }, 280);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const isIngestionActive = Boolean(
    liveJob &&
      (liveJob.status === "PENDING" ||
        liveJob.status === "RUNNING" ||
        liveJob.status === "RETRYING")
  );

  const handlePullTrades = async () => {
    if (isPullSubmitting || isIngestionActive) return;
    setIsPullSubmitting(true);
    setActionError(null);
    setBannerDismissed(false);

    try {
      const response = await triggerPullTrades();
      setLiveJob((prev) => {
        if (prev && prev.job_id === response.job_id) return prev;
        return {
          job_id: response.job_id,
          status: response.status,
          progress: 0,
          stage: "Queued",
          message: response.message,
          delay_seconds: response.estimated_delay_seconds,
          batch_size: response.batch_size,
          records_fetched: 0,
          records_inserted: 0,
          duplicates_skipped: 0,
          attempt_count: 0,
          max_retries: response.max_retries,
          error_message: null,
          created_at: response.created_at,
          started_at: null,
          completed_at: null,
          updated_at: response.created_at,
        };
      });
      void refreshJobsOnly();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setActionError(err.message);
        void refreshJobsOnly();
      } else {
        setActionError(
          err instanceof Error
            ? err.message
            : "Failed to initiate asynchronous BSE trade pull."
        );
      }
    } finally {
      setIsPullSubmitting(false);
    }
  };

  const handleSortChange = (field: TradeSortField) => {
    setQuery((prev) => ({
      ...prev,
      page: 1,
      sort_by: field,
      sort_order:
        prev.sort_by === field && prev.sort_order === "desc" ? "asc" : "desc",
    }));
  };

  const handleResetFilters = () => {
    setSearchInput("");
    setQuery((prev) => ({
      ...prev,
      page: 1,
      search: "",
      symbol: "",
      client: "",
    }));
  };

  const visibleBannerJob = bannerDismissed && !isIngestionActive ? null : liveJob;

  return (
    <div className="app-shell">
      <Header
        connectionStatus={connectionStatus}
        lastSuccessfulSync={lastSuccessfulSync}
        isIngestionActive={isIngestionActive}
        isPullSubmitting={isPullSubmitting}
        onPullTrades={handlePullTrades}
      />

      <main className="container main-content">
        <IngestionStatusBanner
          job={visibleBannerJob}
          actionError={bannerDismissed ? null : actionError}
          isPullSubmitting={isPullSubmitting}
          onRetryPull={handlePullTrades}
          onDismiss={() => {
            setBannerDismissed(true);
            setActionError(null);
          }}
        />

        <KpiGrid
          summary={tradesData?.summary ?? null}
          isLoading={isTradesLoading}
        />

        <LatestTradesStrip
          trades={latestTrades}
          isLoading={isLatestLoading}
        />

        <TradeLedger
          data={tradesData}
          filters={filters}
          query={query}
          searchInput={searchInput}
          isLoading={isTradesLoading}
          error={tradesError}
          onSearchInputChange={setSearchInput}
          onSymbolChange={(symbol) =>
            setQuery((prev) => ({ ...prev, symbol, page: 1 }))
          }
          onClientChange={(client) =>
            setQuery((prev) => ({ ...prev, client, page: 1 }))
          }
          onSortChange={handleSortChange}
          onPageChange={(page) => setQuery((prev) => ({ ...prev, page }))}
          onPageSizeChange={(page_size) =>
            setQuery((prev) => ({ ...prev, page_size, page: 1 }))
          }
          onResetFilters={handleResetFilters}
          onRetryFetch={() => void loadTrades(query)}
        />

        <IngestionHistory
          jobs={jobs}
          isLoading={isJobsLoading}
          error={jobsError}
          onRetryLoad={() => void refreshJobsOnly()}
        />
      </main>

      <footer className="app-footer">
        <div className="container footer-inner">
          <span>
            Simulated Assessment Data · Indian Equity Symbols (INR) · Not Live Market Feed
          </span>
          <span>SQLite Persistent Ledger · Real-Time Updates via SSE</span>
        </div>
      </footer>
    </div>
  );
}
