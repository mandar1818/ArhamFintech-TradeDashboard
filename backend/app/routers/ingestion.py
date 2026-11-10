from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, status

from app.routers.dependencies import get_ingestion_service
from app.schemas.common import ErrorResponse
from app.schemas.ingestion import (
    IngestionHistoryResponse,
    IngestionJobResponse,
    PullTradesRequest,
    PullTradesResponse,
)
from app.services.ingestion_service import IngestionService

router = APIRouter(tags=["Ingestion"])


@router.post(
    "/pull-trades",
    response_model=PullTradesResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger asynchronous BSE trade ingestion",
    description=(
        "Queues an asynchronous background ingestion job to pull newly settled BSE trades after "
        "the configured exchange delay (default 15 minutes, configurable via BSE_PULL_DELAY_SECONDS). "
        "Returns immediately with a unique job_id without holding the HTTP connection open."
    ),
    responses={
        409: {
            "model": ErrorResponse,
            "description": "Another ingestion job is already pending, running, or retrying.",
        }
    },
)
async def pull_trades(
    payload: Optional[PullTradesRequest] = Body(default=None),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> PullTradesResponse:
    effective_request = payload or PullTradesRequest()
    return await ingestion_service.start_pull_job(effective_request)


@router.get(
    "/jobs",
    response_model=IngestionHistoryResponse,
    summary="List ingestion job history",
    description="Returns persistent SQLite ingestion job history, active job status, and last sync timestamp.",
)
def list_ingestion_jobs(
    limit: int = Query(default=25, ge=1, le=100),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> IngestionHistoryResponse:
    return ingestion_service.get_history(limit=limit)


@router.get(
    "/jobs/{job_id}",
    response_model=IngestionJobResponse,
    summary="Get ingestion job details",
    description="Fetches persistent status and metrics for a single ingestion job by job_id.",
    responses={404: {"model": ErrorResponse, "description": "Job ID not found."}},
)
def get_ingestion_job(
    job_id: str,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> IngestionJobResponse:
    return ingestion_service.get_job(job_id)
