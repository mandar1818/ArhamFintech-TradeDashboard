import asyncio
import json
from typing import Dict, List, Tuple

import httpx


class ASGISSEStreamHarness:
    """
    Lightweight real-time ASGI client for testing the FastAPI /events SSE endpoint
    without blocking until infinite stream termination.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.status_code: int | None = None
        self.headers: Dict[str, str] = {}
        self.frames: asyncio.Queue[str] = asyncio.Queue()
        self._disconnect_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        started_event = asyncio.Event()
        buffer = ""

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/events",
            "raw_path": b"/events",
            "query_string": b"",
            "headers": [(b"accept", b"text/event-stream")],
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
        }

        request_sent = False

        async def receive():
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await self._disconnect_event.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            nonlocal buffer
            if message["type"] == "http.response.start":
                self.status_code = message["status"]
                self.headers = {
                    k.decode("latin-1").lower(): v.decode("latin-1")
                    for k, v in message.get("headers", [])
                }
                started_event.set()
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"").decode("utf-8")
                if chunk:
                    buffer += chunk
                    while "\n\n" in buffer:
                        raw_event, buffer = buffer.split("\n\n", 1)
                        await self.frames.put(raw_event)

        self._task = asyncio.create_task(self.app(scope, receive, send))
        await asyncio.wait_for(started_event.wait(), timeout=2.0)

    async def next_event(self, timeout: float = 3.0) -> Tuple[str, Dict]:
        while True:
            raw = await asyncio.wait_for(self.frames.get(), timeout=timeout)
            if raw.startswith(":"):
                # Skip SSE keepalive comments.
                continue
            event_name = "message"
            data_lines: List[str] = []
            for line in raw.splitlines():
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data_lines.append(line.split(":", 1)[1].strip())
            payload = json.loads("\n".join(data_lines)) if data_lines else {}
            return event_name, payload

    async def close(self) -> None:
        self._disconnect_event.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except asyncio.TimeoutError:
                self._task.cancel()
                await asyncio.gather(self._task, return_exceptions=True)


async def test_sse_streams_completion_to_multiple_clients_and_cleans_up(app_factory) -> None:
    app, _ = app_factory(
        seed_trade_count=3000,
        bse_pull_delay_seconds=0.25,
        bse_default_batch_size=15,
    )
    async with app.router.lifespan_context(app):
        client_one = ASGISSEStreamHarness(app)
        client_two = ASGISSEStreamHarness(app)

        await client_one.connect()
        await client_two.connect()

        try:
            assert client_one.status_code == 200
            assert "text/event-stream" in client_one.headers["content-type"]
            assert client_one.headers["cache-control"] == "no-cache"

            ev1, payload1 = await client_one.next_event()
            ev2, payload2 = await client_two.next_event()
            assert ev1 == "connected"
            assert ev2 == "connected"
            assert payload1["active_job"] is None
            assert app.state.sse_broker.subscriber_count == 2

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
                pull_resp = await http.post("/pull-trades")
                assert pull_resp.status_code == 202
                job_id = pull_resp.json()["job_id"]

            async def collect_until_terminal(harness: ASGISSEStreamHarness) -> List[Tuple[str, Dict]]:
                events: List[Tuple[str, Dict]] = []
                while True:
                    ev_name, data = await harness.next_event(timeout=5.0)
                    events.append((ev_name, data))
                    if ev_name in ("job_completed", "job_failed"):
                        return events

            events_one, events_two = await asyncio.gather(
                collect_until_terminal(client_one),
                collect_until_terminal(client_two),
            )

            names_one = [name for name, _ in events_one]
            names_two = [name for name, _ in events_two]

            assert "job_started" in names_one
            assert "job_progress" in names_one
            assert events_one[-1][0] == "job_completed"
            assert events_one[-1][1]["job_id"] == job_id
            assert events_one[-1][1]["records_inserted"] == 15

            assert events_two[-1][0] == "job_completed"
            assert events_two[-1][1]["job_id"] == job_id
        finally:
            await client_one.close()
            await client_two.close()

        # Verify clean SSE unsubscription on disconnect.
        await asyncio.sleep(0.05)
        assert app.state.sse_broker.subscriber_count == 0


async def test_sse_emits_retrying_and_failed_events_on_error(app_factory) -> None:
    app, _ = app_factory(
        seed_trade_count=3000,
        bse_pull_delay_seconds=0.15,
        bse_max_retries=1,
        bse_retry_delay_seconds=0.05,
    )
    async with app.router.lifespan_context(app):
        stream = ASGISSEStreamHarness(app)
        await stream.connect()
        try:
            ev, _ = await stream.next_event()
            assert ev == "connected"

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
                resp = await http.post("/pull-trades", json={"simulate_failure": True})
                assert resp.status_code == 202
                job_id = resp.json()["job_id"]

            seen: List[Tuple[str, Dict]] = []
            while True:
                ev_name, data = await stream.next_event(timeout=5.0)
                seen.append((ev_name, data))
                if ev_name in ("job_completed", "job_failed"):
                    break

            event_names = [n for n, _ in seen]
            assert "job_retrying" in event_names
            assert seen[-1][0] == "job_failed"
            assert seen[-1][1]["job_id"] == job_id
            assert seen[-1][1]["status"] == "FAILED"
            assert seen[-1][1]["error_message"]
        finally:
            await stream.close()
