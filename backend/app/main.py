from contextlib import asynccontextmanager
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    DuplicateIngestionJobError,
    JobNotFoundError,
    duplicate_job_exception_handler,
    http_exception_handler,
    job_not_found_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.database.session import create_db_engine, create_session_factory, init_db
from app.routers import events, health, ingestion, trades
from app.services.bse_mock_service import BSEMockService
from app.services.ingestion_service import IngestionService
from app.services.seed_service import seed_initial_trades_if_empty
from app.services.sse_broker import SSEBroker

logger = logging.getLogger(__name__)


def create_app(
    settings_override: Optional[Settings] = None,
    bse_mock_override: Optional[BSEMockService] = None,
) -> FastAPI:
    """Application factory creating a fully wired FastAPI instance."""
    settings = settings_override or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_db_engine(settings.database_url)
        session_factory = create_session_factory(engine)
        init_db(engine)

        seeded_count = seed_initial_trades_if_empty(
            session_factory=session_factory,
            seed_count=settings.seed_trade_count,
        )

        sse_broker = SSEBroker()
        ingestion_service = IngestionService(
            session_factory=session_factory,
            sse_broker=sse_broker,
            settings=settings,
            bse_mock_service=bse_mock_override,
        )
        ingestion_service.recover_interrupted_jobs()

        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.sse_broker = sse_broker
        app.state.ingestion_service = ingestion_service

        logger.info(
            "Backend application started",
            extra={
                "seeded_trades": seeded_count,
                "bse_pull_delay_seconds": settings.bse_pull_delay_seconds,
            },
        )
        try:
            yield
        finally:
            await ingestion_service.shutdown()
            engine.dispose()
            logger.info("Backend application shut down cleanly")

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "BSE Trade Operations Dashboard API providing SQLite trade querying, "
            "asynchronous simulated BSE ingestion jobs, and Server-Sent Events (SSE)."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.add_exception_handler(DuplicateIngestionJobError, duplicate_job_exception_handler)
    app.add_exception_handler(JobNotFoundError, job_not_found_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(health.router)
    app.include_router(trades.router)
    app.include_router(ingestion.router)
    app.include_router(events.router)

    return app


app = create_app()
