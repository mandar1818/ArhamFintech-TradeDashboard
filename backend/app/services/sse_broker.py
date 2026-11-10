import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)


def format_sse_message(event_type: str, data: Dict[str, Any], event_id: str | None = None) -> str:
    """Format a structured Server-Sent Events (SSE) wire frame."""
    eid = event_id or uuid.uuid4().hex[:12]
    payload = json.dumps(data, default=str)
    return f"id: {eid}\nevent: {event_type}\ndata: {payload}\n\n"


class SSEBroker:
    """In-memory pub/sub broker fanning out SSE events to all connected dashboard clients."""

    def __init__(self, max_queue_size: int = 100) -> None:
        self._subscribers: Set[asyncio.Queue[str]] = set()
        self._max_queue_size = max_queue_size
        self._lock = asyncio.Lock()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=self._max_queue_size)
        async with self._lock:
            self._subscribers.add(queue)
        logger.info(
            "SSE client subscribed",
            extra={"sse_subscribers": len(self._subscribers)},
        )
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)
        logger.info(
            "SSE client unsubscribed",
            extra={"sse_subscribers": len(self._subscribers)},
        )

    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        frame = format_sse_message(
            event_type=event_type,
            data={
                **data,
                "event_type": event_type,
                "emitted_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        async with self._lock:
            subscribers = list(self._subscribers)

        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                logger.warning("Dropped SSE frame for saturated subscriber queue")
