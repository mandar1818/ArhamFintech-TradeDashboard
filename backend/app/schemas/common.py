from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, BeforeValidator, Field


def ensure_utc_datetime(value: Any) -> Any:
    """Attach UTC timezone to naive datetimes read from SQLite."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return value


UTCDatetime = Annotated[datetime, BeforeValidator(ensure_utc_datetime)]


class ErrorDetail(BaseModel):
    field: str
    message: str
    type: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    request_id: Optional[str] = None
    details: Optional[List[ErrorDetail]] = None
    extra: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str = Field(examples=["healthy"])
    database: str = Field(examples=["connected"])
    total_trades: int
    active_job_id: Optional[str] = None
    sse_subscribers: int
    bse_pull_delay_seconds: float
    timestamp: UTCDatetime
