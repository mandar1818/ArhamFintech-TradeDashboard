from typing import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.ingestion_service import IngestionService
from app.services.sse_broker import SSEBroker


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_db_session(request: Request) -> Generator[Session, None, None]:
    session_factory = request.app.state.session_factory
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def get_ingestion_service(request: Request) -> IngestionService:
    return request.app.state.ingestion_service


def get_sse_broker(request: Request) -> SSEBroker:
    return request.app.state.sse_broker
