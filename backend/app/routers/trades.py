from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.routers.dependencies import get_db_session
from app.schemas.trade import SortOrder, TradeFiltersResponse, TradesResponse, TradeSortField
from app.services.trade_service import get_trade_filters, get_trades

router = APIRouter(tags=["Trades"])


@router.get(
    "/getTrades",
    response_model=TradesResponse,
    summary="Query stored BSE trades",
    description=(
        "Returns stored BSE equity trades immediately from SQLite with server-side pagination, "
        "search, symbol/client filtering, sorting, and portfolio summary metrics. "
        "Never blocks on asynchronous BSE ingestion jobs."
    ),
)
def read_trades(
    page: int = Query(default=1, ge=1, description="1-based page number."),
    page_size: int = Query(default=25, ge=1, le=200, description="Number of trades per page."),
    search: Optional[str] = Query(
        default=None,
        max_length=100,
        description="Case-insensitive search across trade_id, symbol, and client.",
    ),
    symbol: Optional[str] = Query(
        default=None,
        max_length=32,
        description="Exact stock symbol filter (e.g. RELIANCE, TCS).",
    ),
    client: Optional[str] = Query(
        default=None,
        max_length=128,
        description="Exact client filter.",
    ),
    sort_by: TradeSortField = Query(
        default=TradeSortField.TIMESTAMP,
        description="Column to sort trades by.",
    ),
    sort_order: SortOrder = Query(
        default=SortOrder.DESC,
        description="Sort direction (asc or desc).",
    ),
    db: Session = Depends(get_db_session),
) -> TradesResponse:
    return get_trades(
        db,
        page=page,
        page_size=page_size,
        search=search,
        symbol=symbol,
        client=client,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/trades/filters",
    response_model=TradeFiltersResponse,
    summary="List available symbol and client filters",
    description="Returns distinct stock symbols and institutional clients present in SQLite.",
)
def read_trade_filters(db: Session = Depends(get_db_session)) -> TradeFiltersResponse:
    return get_trade_filters(db)
