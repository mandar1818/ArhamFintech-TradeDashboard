import type { IngestionJob, JobStatus } from "../types/trade";
import {
  formatDuration,
  formatInteger,
  formatTimestampIST,
} from "../utils/format";

interface IngestionHistoryProps {
  jobs: IngestionJob[];
  isLoading: boolean;
  error: string | null;
  onRetryLoad: () => void;
}

const STATUS_BADGE_CLASS: Record<JobStatus, string> = {
  PENDING: "badge-info",
  RUNNING: "badge-info",
  RETRYING: "badge-warning",
  COMPLETED: "badge-success",
  FAILED: "badge-danger",
};

export function IngestionHistory({
  jobs,
  isLoading,
  error,
  onRetryLoad,
}: IngestionHistoryProps) {
  return (
    <section className="card" aria-label="Asynchronous pull history">
      <div className="card-header">
        <div className="card-title-group">
          <h2 className="card-title">Ingestion Pull History</h2>
          <p className="card-subtitle">
            Persistent SQLite audit log of asynchronous trade pull jobs and errors
          </p>
        </div>
        <span className="badge badge-neutral tabular-nums">
          {jobs.length} Recorded {jobs.length === 1 ? "Job" : "Jobs"}
        </span>
      </div>

      {error && jobs.length === 0 ? (
        <div className="state-box state-box-compact">
          <p className="state-desc">{error}</p>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onRetryLoad}
          >
            Retry
          </button>
        </div>
      ) : isLoading && jobs.length === 0 ? (
        <div className="state-box state-box-compact">
          <p className="state-desc">Loading ingestion job history...</p>
        </div>
      ) : jobs.length === 0 ? (
        <div className="state-box state-box-compact">
          <h3 className="state-title">No Ingestion Pulls Executed Yet</h3>
          <p className="state-desc">
            Use &ldquo;Pull BSE Trades&rdquo; above to start an asynchronous pull.
            Currently displaying initial seeded records.
          </p>
        </div>
      ) : (
        <>
          {error && (
            <div className="inline-error-bar">
              <span>{error}</span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={onRetryLoad}
              >
                Retry
              </button>
            </div>
          )}
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Status</th>
                  <th>Stage / Error</th>
                  <th className="th-right">Inserted / Fetched</th>
                  <th className="th-right">Duplicates Skipped</th>
                  <th className="th-right">Attempts</th>
                  <th>Duration</th>
                  <th>Completed (IST)</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td className="mono">{job.job_id}</td>
                    <td>
                      <span className={`badge ${STATUS_BADGE_CLASS[job.status]}`}>
                        {job.status}
                      </span>
                    </td>
                    <td className={job.status === "FAILED" ? "error-cell" : ""}>
                      {job.status === "FAILED" && job.error_message
                        ? job.error_message
                        : job.stage}
                    </td>
                    <td className="td-right tabular-nums">
                      {formatInteger(job.records_inserted)} /{" "}
                      {formatInteger(job.records_fetched)}
                    </td>
                    <td className="td-right tabular-nums">
                      {formatInteger(job.duplicates_skipped)}
                    </td>
                    <td className="td-right tabular-nums">
                      {job.attempt_count} / {1 + job.max_retries}
                    </td>
                    <td className="tabular-nums">
                      {formatDuration(job.started_at, job.completed_at)}
                    </td>
                    <td className="tabular-nums">
                      {formatTimestampIST(job.completed_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
