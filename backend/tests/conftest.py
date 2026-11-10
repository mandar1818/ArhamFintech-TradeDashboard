from pathlib import Path
from typing import Callable, Tuple

import pytest
from fastapi import FastAPI

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def app_factory(tmp_path: Path) -> Callable[..., Tuple[FastAPI, Path]]:
    """Build isolated FastAPI app instances backed by temporary per-test SQLite files."""

    def _create(
        *,
        db_name: str = "test_trades.db",
        seed_trade_count: int = 3050,
        bse_pull_delay_seconds: float = 0.25,
        bse_default_batch_size: int = 20,
        bse_max_retries: int = 1,
        bse_retry_delay_seconds: float = 0.05,
        sse_heartbeat_seconds: float = 5.0,
    ) -> Tuple[FastAPI, Path]:
        db_path = tmp_path / db_name
        settings = Settings(
            app_name="Test BSE Trade API",
            app_env="test",
            log_level="WARNING",
            database_url=f"sqlite:///{db_path.as_posix()}",
            seed_trade_count=seed_trade_count,
            bse_pull_delay_seconds=bse_pull_delay_seconds,
            bse_default_batch_size=bse_default_batch_size,
            bse_max_retries=bse_max_retries,
            bse_retry_delay_seconds=bse_retry_delay_seconds,
            sse_heartbeat_seconds=sse_heartbeat_seconds,
            cors_origins="http://localhost:5173",
        )
        return create_app(settings_override=settings), db_path

    return _create
