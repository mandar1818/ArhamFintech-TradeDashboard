import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "../api/client";
import type {
  IngestionJob,
  SSEConnectedSnapshot,
  SSEConnectionStatus,
} from "../types/trade";

interface UseTradeEventsOptions {
  onIngestionCompleted: (job: IngestionJob) => void;
  onIngestionFailed: (job: IngestionJob) => void;
  onSnapshotSync?: (snapshot: SSEConnectedSnapshot) => void;
}

interface UseTradeEventsResult {
  connectionStatus: SSEConnectionStatus;
  liveJob: IngestionJob | null;
  setLiveJob: React.Dispatch<React.SetStateAction<IngestionJob | null>>;
}

function isJobActiveStatus(status: IngestionJob["status"]): boolean {
  return status === "PENDING" || status === "RUNNING" || status === "RETRYING";
}

export function useTradeEvents({
  onIngestionCompleted,
  onIngestionFailed,
  onSnapshotSync,
}: UseTradeEventsOptions): UseTradeEventsResult {
  const [connectionStatus, setConnectionStatus] =
    useState<SSEConnectionStatus>("connecting");
  const [liveJob, setLiveJob] = useState<IngestionJob | null>(null);

  const onCompletedRef = useRef(onIngestionCompleted);
  const onFailedRef = useRef(onIngestionFailed);
  const onSnapshotRef = useRef(onSnapshotSync);
  const liveJobRef = useRef<IngestionJob | null>(null);
  const lastCompletedJobIdRef = useRef<string | null>(null);
  const lastFailedJobIdRef = useRef<string | null>(null);
  const hasConnectedOnceRef = useRef(false);

  onCompletedRef.current = onIngestionCompleted;
  onFailedRef.current = onIngestionFailed;
  onSnapshotRef.current = onSnapshotSync;
  liveJobRef.current = liveJob;

  useEffect(() => {
    let isUnmounted = false;
    let eventSource: EventSource | null = null;
    let reconnectTimer: number | null = null;
    let reconnectAttempt = 0;

    const clearReconnectTimer = () => {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    const parsePayload = <T,>(raw: string): T | null => {
      try {
        return JSON.parse(raw) as T;
      } catch {
        return null;
      }
    };

    const connect = () => {
      if (isUnmounted) return;
      clearReconnectTimer();

      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }

      setConnectionStatus(hasConnectedOnceRef.current ? "reconnecting" : "connecting");
      const es = new EventSource(`${API_BASE_URL}/events`);
      eventSource = es;

      es.onopen = () => {
        if (isUnmounted) return;
        reconnectAttempt = 0;
        setConnectionStatus("connected");
      };

      const handleConnected = (event: MessageEvent) => {
        if (isUnmounted) return;
        const snapshot = parsePayload<SSEConnectedSnapshot>(event.data);
        if (!snapshot) return;

        setConnectionStatus("connected");

        const latestJob = snapshot.latest_job;
        const latestCompletedId =
          latestJob?.status === "COMPLETED" ? latestJob.job_id : null;
        const latestFailedId =
          latestJob?.status === "FAILED" ? latestJob.job_id : null;

        if (snapshot.active_job) {
          setLiveJob(snapshot.active_job);
        } else if (hasConnectedOnceRef.current && latestJob) {
          if (
            latestCompletedId &&
            latestCompletedId !== lastCompletedJobIdRef.current
          ) {
            lastCompletedJobIdRef.current = latestCompletedId;
            setLiveJob(latestJob);
            onCompletedRef.current(latestJob);
          } else if (
            latestFailedId &&
            latestFailedId !== lastFailedJobIdRef.current &&
            liveJobRef.current &&
            isJobActiveStatus(liveJobRef.current.status)
          ) {
            lastFailedJobIdRef.current = latestFailedId;
            setLiveJob(latestJob);
            onFailedRef.current(latestJob);
          }
        } else if (!hasConnectedOnceRef.current) {
          if (latestCompletedId) {
            lastCompletedJobIdRef.current = latestCompletedId;
          }
          if (latestFailedId) {
            lastFailedJobIdRef.current = latestFailedId;
          }
        }

        hasConnectedOnceRef.current = true;
        onSnapshotRef.current?.(snapshot);
      };

      const handleJobUpdate = (event: MessageEvent) => {
        if (isUnmounted) return;
        const job = parsePayload<IngestionJob>(event.data);
        if (job) {
          setLiveJob(job);
        }
      };

      const handleJobCompleted = (event: MessageEvent) => {
        if (isUnmounted) return;
        const job = parsePayload<IngestionJob>(event.data);
        if (!job) return;
        lastCompletedJobIdRef.current = job.job_id;
        setLiveJob(job);
        onCompletedRef.current(job);
      };

      const handleJobFailed = (event: MessageEvent) => {
        if (isUnmounted) return;
        const job = parsePayload<IngestionJob>(event.data);
        if (!job) return;
        lastFailedJobIdRef.current = job.job_id;
        setLiveJob(job);
        onFailedRef.current(job);
      };

      es.addEventListener("connected", handleConnected);
      es.addEventListener("job_queued", handleJobUpdate);
      es.addEventListener("job_started", handleJobUpdate);
      es.addEventListener("job_progress", handleJobUpdate);
      es.addEventListener("job_retrying", handleJobUpdate);
      es.addEventListener("job_completed", handleJobCompleted);
      es.addEventListener("job_failed", handleJobFailed);

      es.onerror = () => {
        if (isUnmounted) return;
        if (es.readyState === EventSource.CONNECTING) {
          setConnectionStatus("reconnecting");
          return;
        }
        // Stream permanently closed; schedule single-shot exponential backoff reconnect.
        es.close();
        setConnectionStatus("reconnecting");
        const delayMs = Math.min(1000 * Math.pow(2, reconnectAttempt), 15000);
        reconnectAttempt += 1;
        reconnectTimer = window.setTimeout(() => {
          connect();
        }, delayMs);
      };
    };

    connect();

    return () => {
      isUnmounted = true;
      clearReconnectTimer();
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      setConnectionStatus("disconnected");
    };
  }, []);

  return { connectionStatus, liveJob, setLiveJob };
}
