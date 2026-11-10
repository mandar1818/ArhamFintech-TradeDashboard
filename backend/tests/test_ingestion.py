import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import time

import httpx
from sqlalchemy import select

from app.models.ingestion_job import IngestionJob, JobStatus
from app.services.bse_mock_service import RawTradeRecord


async def _wait_for_job_terminal(
    client: httpx.AsyncClient, job_id: str, timeout_seconds: float = 5.0
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        resp = await client.get(f"/jobs/{job_id}")
        assert resp.status_code == 200
        payload = resp.json()
        if payload["status"] in ("COMPLETED", "FAILED"):
            return payload
        await asyncio.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish within {timeout_seconds}s")


async def test_pull_trades_returns_immediately_and_persists_job(app_factory) -> None:
    app, _ = app_factory(seed_trade_count=3000, bse_pull_delay_seconds=15.0)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            started = time.perf_counter()
            resp = await client.post("/pull-trades")
            elapsed = time.perf_counter() - started

            assert resp.status_code == 202
            assert elapsed < 1.0
            body = resp.json()
            assert body["job_id"].startswith("job-")
            assert body["status"] == "PENDING"
            assert body["estimated_delay_seconds"] == 15.0
            assert body["max_retries"] == 1

            job_resp = await client.get(f"/jobs/{body['job_id']}")
            assert job_resp.status_code == 200
            assert job_resp.json()["job_id"] == body["job_id"]


async def test_background_ingestion_persists_only_after_completion(app_factory) -> None:
    app, _ = app_factory(
        seed_trade_count=3000,
        bse_pull_delay_seconds=0.35,
        bse_default_batch_size=25,
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            pull_resp = await client.post("/pull-trades")
            assert pull_resp.status_code == 202
            job_id = pull_resp.json()["job_id"]

            # Immediately mid-flight, new trades must NOT yet be persisted in SQLite.
            mid_trades = await client.get("/getTrades")
            assert mid_trades.json()["total"] == 3000

            finished = await _wait_for_job_terminal(client, job_id)
            assert finished["status"] == "COMPLETED"
            assert finished["progress"] == 100
            assert finished["records_fetched"] == 25
            assert finished["records_inserted"] == 25
            assert finished["duplicates_skipped"] == 0
            assert finished["completed_at"] is not None

            after_trades = await client.get("/getTrades")
            after_json = after_trades.json()
            assert after_json["total"] == 3025
            assert after_json["items"][0]["source"] == "BSE_PULL"

            history_resp = await client.get("/jobs")
            assert history_resp.status_code == 200
            history = history_resp.json()
            assert history["active_job"] is None
            assert history["last_successful_sync"] is not None
            assert history["jobs"][0]["job_id"] == job_id


async def test_duplicate_simultaneous_pull_is_rejected_with_409(app_factory) -> None:
    app, _ = app_factory(seed_trade_count=3000, bse_pull_delay_seconds=5.0)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post("/pull-trades")
            assert first.status_code == 202
            first_job_id = first.json()["job_id"]

            second = await client.post("/pull-trades")
            assert second.status_code == 409
            err = second.json()
            assert err["error"] == "ingestion_already_in_progress"
            assert err["active_job_id"] == first_job_id


async def test_duplicate_trade_ids_prevented_inside_transaction(app_factory) -> None:
    app, _ = app_factory(seed_trade_count=3000, bse_pull_delay_seconds=0.1)
    async with app.router.lifespan_context(app):
        ingestion_service = app.state.ingestion_service
        now = datetime.now(timezone.utc)

        # Create a persistent job row to attach the transactional batch to.
        with app.state.session_factory.begin() as db:
            db.add(
                IngestionJob(
                    job_id="job-dedup-test",
                    status=JobStatus.RUNNING.value,
                    progress=50,
                    stage="Testing Deduplication",
                    message="Dedup test",
                    delay_seconds=0.1,
                    batch_size=6,
                    max_retries=0,
                    created_at=now,
                    updated_at=now,
                )
            )

        batch = [
            # Two trades colliding with seeded trade_ids
            RawTradeRecord("BSE-SEED-000001", "HDFC Mutual Fund", "RELIANCE", 100, Decimal("1310.00"), now),
            RawTradeRecord("BSE-SEED-000002", "SBI Mutual Fund", "TCS", 50, Decimal("4050.00"), now),
            # Three brand-new unique trades + 1 duplicate within the batch itself
            RawTradeRecord("BSE-DEDUP-0001", "HDFC Mutual Fund", "INFY", 120, Decimal("1850.50"), now),
            RawTradeRecord("BSE-DEDUP-0002", "Axis Asset Management", "SBIN", 300, Decimal("820.25"), now),
            RawTradeRecord("BSE-DEDUP-0003", "Kotak Institutional Equities", "ITC", 500, Decimal("490.00"), now),
            RawTradeRecord("BSE-DEDUP-0001", "HDFC Mutual Fund", "INFY", 120, Decimal("1850.50"), now),
        ]

        inserted, skipped, job_res = ingestion_service.persist_trades_atomic(
            job_id="job-dedup-test",
            raw_trades=batch,
        )
        assert inserted == 3
        assert skipped == 3
        assert job_res.status == "COMPLETED"
        assert job_res.records_inserted == 3
        assert job_res.duplicates_skipped == 3

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            trades = await client.get("/getTrades")
            assert trades.json()["total"] == 3003


async def test_failed_ingestion_rolls_back_and_allows_subsequent_pull(app_factory) -> None:
    app, _ = app_factory(
        seed_trade_count=3000,
        bse_pull_delay_seconds=0.2,
        bse_max_retries=1,
        bse_retry_delay_seconds=0.05,
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            fail_resp = await client.post(
                "/pull-trades",
                json={"simulate_failure": True, "batch_size": 20},
            )
            assert fail_resp.status_code == 202
            fail_job_id = fail_resp.json()["job_id"]

            failed_job = await _wait_for_job_terminal(client, fail_job_id)
            assert failed_job["status"] == "FAILED"
            assert failed_job["attempt_count"] == 2  # 1 initial + 1 retry
            assert failed_job["records_inserted"] == 0
            assert "unavailable" in failed_job["error_message"].lower()

            # Zero partial trades were persisted.
            trades_after_fail = await client.get("/getTrades")
            assert trades_after_fail.json()["total"] == 3000

            # Subsequent normal pull succeeds cleanly.
            ok_resp = await client.post("/pull-trades", json={"batch_size": 10})
            assert ok_resp.status_code == 202
            ok_job = await _wait_for_job_terminal(client, ok_resp.json()["job_id"])
            assert ok_job["status"] == "COMPLETED"
            assert ok_job["records_inserted"] == 10


async def test_transient_failure_recovers_via_automatic_retry(app_factory) -> None:
    app, _ = app_factory(
        seed_trade_count=3000,
        bse_pull_delay_seconds=0.2,
        bse_max_retries=2,
        bse_retry_delay_seconds=0.05,
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/pull-trades",
                json={"simulate_transient_failures": 1, "batch_size": 12},
            )
            assert resp.status_code == 202
            job_id = resp.json()["job_id"]

            finished = await _wait_for_job_terminal(client, job_id)
            assert finished["status"] == "COMPLETED"
            assert finished["attempt_count"] == 2
            assert finished["records_inserted"] == 12

            with app.state.session_factory() as db:
                row = db.scalar(select(IngestionJob).where(IngestionJob.job_id == job_id))
                assert row is not None
                assert row.status == "COMPLETED"
                assert row.error_message is None


async def test_unknown_job_404_validation_422_and_crash_recovery(app_factory) -> None:
    app, _ = app_factory(seed_trade_count=3000, bse_pull_delay_seconds=0.1)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            not_found = await client.get("/jobs/job-does-not-exist")
            assert not_found.status_code == 404
            assert not_found.json()["error"] == "job_not_found"

            bad_query = await client.get("/getTrades", params={"page": 0})
            assert bad_query.status_code == 422
            assert bad_query.json()["error"] == "validation_error"

        # Simulate a stale RUNNING job left behind by an unclean process crash.
        now = datetime.now(timezone.utc)
        with app.state.session_factory.begin() as db:
            db.add(
                IngestionJob(
                    job_id="job-stale-crash",
                    status=JobStatus.RUNNING.value,
                    progress=40,
                    stage="Downloading",
                    message="In progress before crash",
                    delay_seconds=10.0,
                    batch_size=10,
                    max_retries=1,
                    created_at=now,
                    updated_at=now,
                )
            )

        recovered = app.state.ingestion_service.recover_interrupted_jobs()
        assert recovered == 1
        stale_after = app.state.ingestion_service.get_job("job-stale-crash")
        assert stale_after.status == "FAILED"

