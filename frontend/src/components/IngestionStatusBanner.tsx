import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  RotateCcw,
  X,
} from "lucide-react";
import type { IngestionJob } from "../types/trade";
import { formatTimestampIST } from "../utils/format";

interface IngestionStatusBannerProps {
  job: IngestionJob | null;
  actionError: string | null;
  isPullSubmitting: boolean;
  onRetryPull: () => void;
  onDismiss: () => void;
}

export function IngestionStatusBanner({
  job,
  actionError,
  isPullSubmitting,
  onRetryPull,
  onDismiss,
}: IngestionStatusBannerProps) {
  if (!job && !actionError) {
    return null;
  }

  if (actionError && (!job || job.status === "COMPLETED")) {
    return (
      <section className="status-banner failed" role="alert">
        <div className="status-banner-top">
          <div className="status-banner-info">
            <AlertCircle size={18} className="banner-icon banner-icon-danger" />
            <div>
              <h2 className="status-banner-title">Unable to Start Ingestion Job</h2>
              <p className="status-banner-desc">{actionError}</p>
            </div>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onDismiss}
            aria-label="Dismiss error"
          >
            <X size={14} />
          </button>
        </div>
      </section>
    );
  }

  if (!job) return null;

  const statusLower = job.status.toLowerCase();
  const isActive =
    job.status === "PENDING" ||
    job.status === "RUNNING" ||
    job.status === "RETRYING";

  const renderIcon = () => {
    if (job.status === "COMPLETED") {
      return <CheckCircle2 size={18} className="banner-icon banner-icon-success" />;
    }
    if (job.status === "FAILED") {
      return <AlertCircle size={18} className="banner-icon banner-icon-danger" />;
    }
    return (
      <Loader2
        size={18}
        className={`spin banner-icon ${
          job.status === "RETRYING" ? "banner-icon-warning" : "banner-icon-info"
        }`}
      />
    );
  };

  const titleText = (() => {
    switch (job.status) {
      case "PENDING":
        return `Ingestion Queued — ${job.stage}`;
      case "RUNNING":
        return `Ingestion Running — ${job.stage}`;
      case "RETRYING":
        return `Upstream Error — ${job.stage}`;
      case "COMPLETED":
        return "Ingestion Pull Completed";
      case "FAILED":
        return "Ingestion Pull Failed";
    }
  })();

  return (
    <section className={`status-banner ${statusLower}`} aria-live="polite">
      <div className="status-banner-top">
        <div className="status-banner-info">
          {renderIcon()}
          <div>
            <h2 className="status-banner-title">{titleText}</h2>
            <p className="status-banner-desc">
              {job.status === "FAILED" && job.error_message
                ? job.error_message
                : job.message}
            </p>
          </div>
        </div>

        <div className="status-banner-actions">
          {job.status === "FAILED" && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={isPullSubmitting}
              onClick={onRetryPull}
            >
              <RotateCcw size={13} />
              <span>Retry Pull</span>
            </button>
          )}
          {!isActive && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={onDismiss}
              aria-label="Dismiss notification"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {isActive && (
        <div
          className="progress-track"
          role="progressbar"
          aria-valuenow={job.progress}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="progress-fill"
            style={{ width: `${Math.max(job.progress, 5)}%` }}
          />
        </div>
      )}

      <div className="status-meta-row tabular-nums">
        <span>
          Job ID: <span className="mono">{job.job_id}</span> · Batch:{" "}
          {job.batch_size} trades · Attempt {Math.max(job.attempt_count, 1)}/
          {1 + job.max_retries}
        </span>
        <span>
          {isActive
            ? `${job.progress}% · Simulated window ${job.delay_seconds}s`
            : job.status === "COMPLETED"
              ? `Inserted ${job.records_inserted} (${job.duplicates_skipped} skipped) · ${formatTimestampIST(job.completed_at)}`
              : `Stopped at ${formatTimestampIST(job.completed_at || job.updated_at)}`}
        </span>
      </div>
    </section>
  );
}
