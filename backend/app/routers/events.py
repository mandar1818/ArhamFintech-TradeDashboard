import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.config import Settings
from app.routers.dependencies import (
    get_ingestion_service,
    get_settings_dep,
    get_sse_broker,
)
from app.services.ingestion_service import IngestionService
from app.services.sse_broker import SSEBroker, format_sse_message

router = APIRouter(tags=["Real-Time Events"])


@router.get(
    "/events",
    summary="Subscribe to real-time ingestion events (SSE)",
    description=(
        "Server-Sent Events (SSE) stream notifying all connected dashboard clients when "
        "ingestion starts, progresses, retries, completes, or fails."
    ),
)
async def stream_events(
    request: Request,
    sse_broker: SSEBroker = Depends(get_sse_broker),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    settings: Settings = Depends(get_settings_dep),
) -> StreamingResponse:
    queue = await sse_broker.subscribe()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            initial_snapshot = ingestion_service.get_connection_snapshot()
            initial_snapshot["server_time"] = datetime.now(timezone.utc).isoformat()
            yield format_sse_message("connected", initial_snapshot)

            while True:
                if await request.is_disconnected():
                    break
                try:
                    frame = await asyncio.wait_for(
                        queue.get(),
                        timeout=settings.sse_heartbeat_seconds,
                    )
                    yield frame
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": heartbeat\n\n"
        finally:
            await sse_broker.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
