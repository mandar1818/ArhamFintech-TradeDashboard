import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.exceptions import (
    BSEUpstreamError,
    DuplicateIngestionJobError,
    JobNotFoundError,
)
from app.models.ingestion_job import ACTIVE_JOB_STATUSES, IngestionJob, JobStatus
from app.models.trade import Trade
from app.schemas.ingestion import (
    IngestionHistoryResponse,
    IngestionJobResponse,
    PullTradesRequest,
    PullTradesResponse,
)
from app.services.bse_mock_service import BSEMockService, RawTradeRecord
from app.services.sse_broker import SSEBroker

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_job_response(job: IngestionJob) -> IngestionJobResponse:
    return IngestionJobResponse.model_validate(job)


class IngestionService:
    """Manages asynchronous BSE trade ingestion jobs, SQLite persistence, retries, and SSE events."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        sse_broker: SSEBroker,
        settings: Settings,
        bse_mock_service: Optional[BSEMockService] = None,
    ) -> None:
        self._session_factory = session_factory
        self._sse_broker = sse_broker
        self._settings = settings
        self._bse_mock = bse_mock_service or BSEMockService()
        self._create_lock = asyncio.Lock()
        self._tasks: Dict[str, asyncio.Task[None]] = {}

    def recover_interrupted_jobs(self) -> int:
        """
        Mark any leftover active jobs from an unclean process restart as FAILED so
        future ingestion pulls are never blocked by stale DB locks.
        """
        now = _utc_now()
        with self._session_factory.begin() as db:
            stale_jobs = db.scalars(
                select(IngestionJob).where(IngestionJob.status.in_(ACTIVE_JOB_STATUSES))
            ).all()
            for job in stale_jobs:
                job.status = JobStatus.FAILED.value
                job.stage = "Interrupted"
                job.message = "Previous server instance restarted before ingestion completed."
                job.error_message = "Server restarted during ingestion; safe to initiate a new pull."
                job.completed_at = now
                job.updated_at = now
            count = len(stale_jobs)
        if count > 0:
            logger.warning(
                "Recovered interrupted ingestion jobs at startup",
                extra={"recovered_count": count},
            )
        return count

    async def shutdown(self) -> None:
        """Cancel running background ingestion tasks cleanly during application shutdown."""
        pending_tasks = [task for task in self._tasks.values() if not task.done()]
        if not pending_tasks:
            return
        logger.info(
            "Cancelling active ingestion background tasks for shutdown",
            extra={"active_tasks": len(pending_tasks)},
        )
        for task in pending_tasks:
            task.cancel()
        await asyncio.gather(*pending_tasks, return_exceptions=True)
        self._tasks.clear()

    def get_active_job(self) -> Optional[IngestionJobResponse]:
        with self._session_factory() as db:
            job = db.scalar(
                select(IngestionJob)
                .where(IngestionJob.status.in_(ACTIVE_JOB_STATUSES))
                .order_by(desc(IngestionJob.created_at))
            )
            return _to_job_response(job) if job else None

    def get_job(self, job_id: str) -> IngestionJobResponse:
        with self._session_factory() as db:
            job = db.scalar(select(IngestionJob).where(IngestionJob.job_id == job_id))
            if job is None:
                raise JobNotFoundError(job_id)
            return _to_job_response(job)

    def get_history(self, limit: int = 25) -> IngestionHistoryResponse:
        with self._session_factory() as db:
            jobs = db.scalars(
                select(IngestionJob)
                .order_by(desc(IngestionJob.created_at), desc(IngestionJob.id))
                .limit(limit)
            ).all()

            active_job = db.scalar(
                select(IngestionJob)
                .where(IngestionJob.status.in_(ACTIVE_JOB_STATUSES))
                .order_by(desc(IngestionJob.created_at))
            )

            last_completed = db.scalar(
                select(IngestionJob)
                .where(IngestionJob.status == JobStatus.COMPLETED.value)
                .order_by(desc(IngestionJob.completed_at), desc(IngestionJob.id))
            )

            total = int(db.scalar(select(func.count(IngestionJob.id))) or 0)

            return IngestionHistoryResponse(
                active_job=_to_job_response(active_job) if active_job else None,
                last_successful_sync=last_completed.completed_at if last_completed else None,
                jobs=[_to_job_response(job) for job in jobs],
                total=total,
            )

    def get_connection_snapshot(self) -> Dict:
        """Build initial state snapshot sent immediately when an SSE client connects."""
        history = self.get_history(limit=1)
        latest_job = history.jobs[0] if history.jobs else None
        return {
            "active_job": history.active_job.model_dump(mode="json") if history.active_job else None,
            "latest_job": latest_job.model_dump(mode="json") if latest_job else None,
            "last_successful_sync": (
                history.last_successful_sync.isoformat() if history.last_successful_sync else None
            ),
        }

    async def start_pull_job(self, request: PullTradesRequest) -> PullTradesResponse:
        """
        Persist a new ingestion job in SQLite, reject concurrent duplicates with 409,
        launch the async worker, and return immediately without holding the HTTP request open.
        """
        async with self._create_lock:
            now = _utc_now()
            job_id = f"job-{uuid.uuid4().hex[:12]}"
            batch_size = request.batch_size or self._settings.bse_default_batch_size
            delay_seconds = self._settings.bse_pull_delay_seconds

            with self._session_factory() as db:
                active = db.scalar(
                    select(IngestionJob).where(IngestionJob.status.in_(ACTIVE_JOB_STATUSES))
                )
                if active is not None:
                    raise DuplicateIngestionJobError(active.job_id, active.status)

                job = IngestionJob(
                    job_id=job_id,
                    status=JobStatus.PENDING.value,
                    progress=0,
                    stage="Queued",
                    message="Ingestion job queued for asynchronous BSE processing.",
                    delay_seconds=delay_seconds,
                    batch_size=batch_size,
                    max_retries=self._settings.bse_max_retries,
                    simulate_failure=request.simulate_failure,
                    simulate_transient_failures=request.simulate_transient_failures,
                    created_at=now,
                    updated_at=now,
                )
                db.add(job)
                try:
                    db.commit()
                except IntegrityError as exc:
                    db.rollback()
                    active = db.scalar(
                        select(IngestionJob).where(IngestionJob.status.in_(ACTIVE_JOB_STATUSES))
                    )
                    if active is not None:
                        raise DuplicateIngestionJobError(active.job_id, active.status) from exc
                    raise

            task = asyncio.create_task(self._execute_job(job_id), name=f"bse-ingestion-{job_id}")
            self._tasks[job_id] = task
            task.add_done_callback(lambda _t, jid=job_id: self._tasks.pop(jid, None))

        job_snapshot = self.get_job(job_id)
        await self._sse_broker.publish("job_queued", job_snapshot.model_dump(mode="json"))

        logger.info(
            "Queued asynchronous BSE trade ingestion job",
            extra={
                "job_id": job_id,
                "delay_seconds": delay_seconds,
                "batch_size": batch_size,
            },
        )

        return PullTradesResponse(
            job_id=job_id,
            status=JobStatus.PENDING.value,
            message="Asynchronous BSE trade ingestion started.",
            estimated_delay_seconds=delay_seconds,
            batch_size=batch_size,
            max_retries=self._settings.bse_max_retries,
            created_at=now,
        )

    def _update_job_state(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        stage: Optional[str] = None,
        message: Optional[str] = None,
        attempt_count: Optional[int] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> IngestionJobResponse:
        now = _utc_now()
        with self._session_factory.begin() as db:
            job = db.scalar(select(IngestionJob).where(IngestionJob.job_id == job_id))
            if job is None:
                raise JobNotFoundError(job_id)
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = progress
            if stage is not None:
                job.stage = stage
            if message is not None:
                job.message = message
            if attempt_count is not None:
                job.attempt_count = attempt_count
            if error_message is not None:
                job.error_message = error_message
            if started_at is not None and job.started_at is None:
                job.started_at = started_at
            if completed_at is not None:
                job.completed_at = completed_at
            job.updated_at = now
        return _to_job_response(job)

    def persist_trades_atomic(
        self,
        *,
        job_id: str,
        raw_trades: List[RawTradeRecord],
    ) -> Tuple[int, int, IngestionJobResponse]:
        """
        Persist newly fetched trades and mark job COMPLETED in one atomic SQLite transaction.
        Prevents duplicate trade_ids both within the incoming batch and against existing rows.
        Returns (inserted_count, duplicates_skipped, updated_job_response).
        """
        now = _utc_now()

        # Deduplicate inside incoming payload while preserving order.
        seen_ids = set()
        unique_trades: List[RawTradeRecord] = []
        for item in raw_trades:
            if item.trade_id in seen_ids:
                continue
            seen_ids.add(item.trade_id)
            unique_trades.append(item)

        with self._session_factory.begin() as db:
            job = db.scalar(select(IngestionJob).where(IngestionJob.job_id == job_id))
            if job is None:
                raise JobNotFoundError(job_id)

            total_inserted = 0
            if unique_trades:
                values = [
                    {
                        "trade_id": t.trade_id,
                        "client": t.client,
                        "symbol": t.symbol,
                        "quantity": t.quantity,
                        "price": t.price,
                        "timestamp": t.timestamp,
                        "source": "BSE_PULL",
                        "job_id": job_id,
                        "created_at": now,
                    }
                    for t in unique_trades
                ]

                chunk_size = 200
                for start in range(0, len(values), chunk_size):
                    chunk = values[start : start + chunk_size]
                    stmt = (
                        sqlite_insert(Trade)
                        .values(chunk)
                        .on_conflict_do_nothing(index_elements=["trade_id"])
                    )
                    result = db.execute(stmt)
                    total_inserted += int(result.rowcount or 0)

            total_fetched = len(raw_trades)
            duplicates_skipped = max(0, total_fetched - total_inserted)

            job.status = JobStatus.COMPLETED.value
            job.progress = 100
            job.stage = "Completed"
            job.message = (
                f"Persisted {total_inserted} new BSE trades"
                + (
                    f" ({duplicates_skipped} duplicates skipped)."
                    if duplicates_skipped > 0
                    else "."
                )
            )
            job.records_fetched = total_fetched
            job.records_inserted = total_inserted
            job.duplicates_skipped = duplicates_skipped
            job.error_message = None
            job.completed_at = now
            job.updated_at = now

            job_response = _to_job_response(job)

        return total_inserted, duplicates_skipped, job_response

    async def _execute_job(self, job_id: str) -> None:
        """Background worker coroutine executing the delayed BSE fetch with retry handling."""
        try:
            with self._session_factory() as db:
                job_row = db.scalar(select(IngestionJob).where(IngestionJob.job_id == job_id))
                if job_row is None:
                    return
                delay_seconds = job_row.delay_seconds
                batch_size = job_row.batch_size
                max_retries = job_row.max_retries
                simulate_failure = job_row.simulate_failure
                simulate_transient_failures = job_row.simulate_transient_failures

            snapshot = self._update_job_state(
                job_id,
                status=JobStatus.RUNNING.value,
                progress=5,
                stage="Initializing Worker",
                message="Background ingestion worker started.",
                started_at=_utc_now(),
            )
            await self._sse_broker.publish("job_started", snapshot.model_dump(mode="json"))

            async def _on_progress(progress: int, stage: str, msg: str) -> None:
                prog_snapshot = self._update_job_state(
                    job_id,
                    progress=progress,
                    stage=stage,
                    message=msg,
                )
                await self._sse_broker.publish("job_progress", prog_snapshot.model_dump(mode="json"))

            total_attempts = 1 + max_retries
            fetched_trades: Optional[List[RawTradeRecord]] = None

            for attempt in range(1, total_attempts + 1):
                if attempt > 1:
                    snapshot = self._update_job_state(
                        job_id,
                        status=JobStatus.RUNNING.value,
                        progress=10,
                        stage=f"Reconnecting (Attempt {attempt}/{total_attempts})",
                        message=f"Retrying BSE exchange pull (attempt {attempt} of {total_attempts}).",
                        attempt_count=attempt,
                    )
                    await self._sse_broker.publish("job_progress", snapshot.model_dump(mode="json"))
                else:
                    self._update_job_state(job_id, attempt_count=attempt)

                try:
                    fetched_trades = await self._bse_mock.fetch_bse_batch(
                        delay_seconds=delay_seconds,
                        batch_size=batch_size,
                        attempt=attempt,
                        simulate_failure=simulate_failure,
                        simulate_transient_failures=simulate_transient_failures,
                        on_progress=_on_progress,
                    )
                    break
                except BSEUpstreamError as exc:
                    logger.warning(
                        "BSE ingestion attempt failed",
                        extra={
                            "job_id": job_id,
                            "attempt": attempt,
                            "max_attempts": total_attempts,
                            "reason": str(exc),
                        },
                    )
                    if attempt < total_attempts and exc.retryable:
                        retry_snapshot = self._update_job_state(
                            job_id,
                            status=JobStatus.RETRYING.value,
                            stage=f"Retry Scheduled ({attempt}/{max_retries})",
                            message=f"BSE feed error; retrying in {self._settings.bse_retry_delay_seconds:.1f}s.",
                            attempt_count=attempt,
                            error_message=str(exc),
                        )
                        await self._sse_broker.publish(
                            "job_retrying", retry_snapshot.model_dump(mode="json")
                        )
                        await asyncio.sleep(self._settings.bse_retry_delay_seconds)
                    else:
                        failed_snapshot = self._update_job_state(
                            job_id,
                            status=JobStatus.FAILED.value,
                            stage="Failed",
                            message="Ingestion failed after exhausting retry attempts.",
                            attempt_count=attempt,
                            error_message=str(exc),
                            completed_at=_utc_now(),
                        )
                        await self._sse_broker.publish(
                            "job_failed", failed_snapshot.model_dump(mode="json")
                        )
                        return

            if fetched_trades is None:
                return

            inserted, skipped, completed_snapshot = self.persist_trades_atomic(
                job_id=job_id,
                raw_trades=fetched_trades,
            )
            logger.info(
                "BSE trade ingestion completed",
                extra={
                    "job_id": job_id,
                    "records_inserted": inserted,
                    "duplicates_skipped": skipped,
                },
            )
            await self._sse_broker.publish("job_completed", completed_snapshot.model_dump(mode="json"))

        except asyncio.CancelledError:
            logger.info("Background ingestion job cancelled", extra={"job_id": job_id})
            try:
                self._update_job_state(
                    job_id,
                    status=JobStatus.FAILED.value,
                    stage="Cancelled",
                    message="Ingestion cancelled due to server shutdown.",
                    error_message="Job cancelled during server shutdown.",
                    completed_at=_utc_now(),
                )
            except Exception:
                pass
            raise
        except Exception:
            logger.exception("Unexpected error during background ingestion", extra={"job_id": job_id})
            try:
                failed_snapshot = self._update_job_state(
                    job_id,
                    status=JobStatus.FAILED.value,
                    stage="Failed",
                    message="Ingestion aborted due to an internal processing error.",
                    error_message="Internal ingestion pipeline error. No partial trades were committed.",
                    completed_at=_utc_now(),
                )
                await self._sse_broker.publish("job_failed", failed_snapshot.model_dump(mode="json"))
            except Exception:
                logger.exception("Failed to record error state for job", extra={"job_id": job_id})
