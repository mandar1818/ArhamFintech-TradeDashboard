from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.routers.dependencies import (
    get_db_session,
    get_ingestion_service,
    get_settings_dep,
    get_sse_broker,
)
from app.schemas.common import HealthResponse
from app.services.ingestion_service import IngestionService
from app.services.sse_broker import SSEBroker
from app.services.trade_service import get_trade_count

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description="Verifies SQLite database connectivity, active ingestion state, and live SSE subscribers.",
)
def health_check(
    db: Session = Depends(get_db_session),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    sse_broker: SSEBroker = Depends(get_sse_broker),
    settings: Settings = Depends(get_settings_dep),
) -> HealthResponse:
    db.execute(text("SELECT 1"))
    total_trades = get_trade_count(db)
    active_job = ingestion_service.get_active_job()
    return HealthResponse(
        status="healthy",
        database="connected",
        total_trades=total_trades,
        active_job_id=active_job.job_id if active_job else None,
        sse_subscribers=sse_broker.subscriber_count,
        bse_pull_delay_seconds=settings.bse_pull_delay_seconds,
        timestamp=datetime.now(timezone.utc),
    )
