from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class JobStatus(str, Enum):
    """Lifecycle states for asynchronous trade ingestion jobs."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ACTIVE_JOB_STATUSES = (JobStatus.PENDING.value, JobStatus.RUNNING.value, JobStatus.RETRYING.value)


class IngestionJob(Base):
    """Persistent state and audit log for asynchronous BSE ingestion pulls."""

    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True, default=JobStatus.PENDING.value)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage: Mapped[str] = mapped_column(String(128), nullable=False, default="Queued")
    message: Mapped[str] = mapped_column(String(512), nullable=False, default="Ingestion job queued.")

    delay_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    records_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    simulate_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    simulate_transient_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(timezone.utc),
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index(
            "ix_ingestion_jobs_single_active",
            text("1"),
            unique=True,
            sqlite_where=text("status IN ('PENDING', 'RUNNING', 'RETRYING')"),
        ),
    )
