from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UTCDatetime


class PullTradesRequest(BaseModel):
    batch_size: Optional[int] = Field(
        default=None,
        ge=1,
        le=500,
        description="Optional override for number of new trades to fetch from BSE.",
    )
    simulate_failure: bool = Field(
        default=False,
        description="When true, simulates a non-recoverable BSE gateway outage for testing.",
    )
    simulate_transient_failures: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Simulates N transient errors before succeeding, useful to verify retry recovery.",
    )


class PullTradesResponse(BaseModel):
    job_id: str = Field(examples=["job-9a8f1b2c3d4e"])
    status: str = Field(examples=["PENDING"])
    message: str
    estimated_delay_seconds: float
    batch_size: int
    max_retries: int
    created_at: UTCDatetime


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    stage: str
    message: str
    delay_seconds: float
    batch_size: int
    records_fetched: int
    records_inserted: int
    duplicates_skipped: int
    attempt_count: int
    max_retries: int
    error_message: Optional[str] = None
    created_at: UTCDatetime
    started_at: Optional[UTCDatetime] = None
    completed_at: Optional[UTCDatetime] = None
    updated_at: UTCDatetime


class IngestionHistoryResponse(BaseModel):
    active_job: Optional[IngestionJobResponse] = None
    last_successful_sync: Optional[UTCDatetime] = None
    jobs: List[IngestionJobResponse]
    total: int = Field(ge=0)
