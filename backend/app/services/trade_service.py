import math
from typing import Optional

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.trade import Trade
from app.schemas.trade import (
    SortOrder,
    TradeFiltersResponse,
    TradeItem,
    TradesResponse,
    TradeSortField,
    TradeSummary,
)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _compute_summary(db: Session, filters: list) -> TradeSummary:
    stmt = select(
        func.count(Trade.id).label("total_trades"),
        func.coalesce(func.sum(Trade.quantity), 0).label("total_quantity"),
        func.coalesce(func.sum(Trade.quantity * Trade.price), 0.0).label("total_value"),
        func.count(func.distinct(Trade.client)).label("unique_clients"),
        func.max(Trade.timestamp).label("latest_trade_at"),
    )
    if filters:
        stmt = stmt.where(*filters)

    row = db.execute(stmt).one()
    return TradeSummary(
        total_trades=int(row.total_trades or 0),
        total_quantity=int(row.total_quantity or 0),
        total_value=round(float(row.total_value or 0.0), 2),
        unique_clients=int(row.unique_clients or 0),
        latest_trade_at=row.latest_trade_at,
    )


def get_trades(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 25,
    search: Optional[str] = None,
    symbol: Optional[str] = None,
    client: Optional[str] = None,
    sort_by: TradeSortField = TradeSortField.TIMESTAMP,
    sort_order: SortOrder = SortOrder.DESC,
) -> TradesResponse:
    """Query stored trades immediately from SQLite with pagination, search, filters, and sorting."""
    filters = []

    if symbol and symbol.strip():
        filters.append(func.upper(Trade.symbol) == symbol.strip().upper())

    if client and client.strip():
        filters.append(Trade.client == client.strip())

    if search and search.strip():
        escaped = f"%{_escape_like(search.strip())}%"
        filters.append(
            or_(
                Trade.trade_id.ilike(escaped, escape="\\"),
                Trade.client.ilike(escaped, escape="\\"),
                Trade.symbol.ilike(escaped, escape="\\"),
            )
        )

    global_summary = _compute_summary(db, [])
    filtered_summary = _compute_summary(db, filters) if filters else global_summary

    total = filtered_summary.total_trades
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    effective_page = min(page, total_pages) if total_pages > 0 else 1

    sort_column_map = {
        TradeSortField.TIMESTAMP: Trade.timestamp,
        TradeSortField.TRADE_ID: Trade.trade_id,
        TradeSortField.CLIENT: Trade.client,
        TradeSortField.SYMBOL: Trade.symbol,
        TradeSortField.QUANTITY: Trade.quantity,
        TradeSortField.PRICE: Trade.price,
        TradeSortField.VALUE: Trade.quantity * Trade.price,
    }
    primary_sort_expr = sort_column_map[sort_by]
    order_fn = asc if sort_order == SortOrder.ASC else desc

    query = select(Trade)
    if filters:
        query = query.where(*filters)

    query = (
        query.order_by(order_fn(primary_sort_expr), desc(Trade.id))
        .offset((effective_page - 1) * page_size)
        .limit(page_size)
    )

    rows = db.scalars(query).all()
    items = [
        TradeItem(
            trade_id=trade.trade_id,
            client=trade.client,
            symbol=trade.symbol,
            quantity=trade.quantity,
            price=round(float(trade.price), 2),
            trade_value=round(float(trade.quantity) * float(trade.price), 2),
            timestamp=trade.timestamp,
            source=trade.source,
        )
        for trade in rows
    ]

    return TradesResponse(
        items=items,
        total=total,
        page=effective_page,
        page_size=page_size,
        total_pages=total_pages,
        summary=global_summary,
        filtered_summary=filtered_summary,
    )


def get_trade_filters(db: Session) -> TradeFiltersResponse:
    """Return distinct stock symbols and client names stored in SQLite."""
    symbols = db.scalars(select(Trade.symbol).distinct().order_by(Trade.symbol.asc())).all()
    clients = db.scalars(select(Trade.client).distinct().order_by(Trade.client.asc())).all()
    return TradeFiltersResponse(symbols=list(symbols), clients=list(clients))


def get_trade_count(db: Session) -> int:
    """Return total stored trade count."""
    return int(db.scalar(select(func.count(Trade.id))) or 0)
