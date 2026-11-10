import logging

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.trade import Trade
from app.services.bse_mock_service import BSEMockService

logger = logging.getLogger(__name__)


def seed_initial_trades_if_empty(
    session_factory: sessionmaker[Session],
    seed_count: int = 3250,
) -> int:
    """
    Seed at least 3,000 realistic Indian stock market trades if the trades table is empty.
    Operation is idempotent and executes in a single atomic transaction.
    """
    if seed_count <= 0:
        return 0

    bse_service = BSEMockService()
    with session_factory.begin() as db:
        existing_count = db.scalar(select(func.count(Trade.id))) or 0
        if existing_count > 0:
            logger.info(
                "Database already seeded; skipping initial seed.",
                extra={"existing_trades": existing_count},
            )
            return 0

        records = bse_service.generate_initial_seed_trades(count=seed_count)
        # Batch in chunks of 500 to stay well within SQLite bind parameter limits.
        chunk_size = 500
        for start in range(0, len(records), chunk_size):
            db.execute(insert(Trade), records[start : start + chunk_size])

    logger.info(
        "Seeded initial BSE trade ledger successfully.",
        extra={"seeded_trades": len(records)},
    )
    return len(records)
