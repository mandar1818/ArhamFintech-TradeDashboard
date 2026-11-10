from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UTCDatetime


class TradeSortField(str, Enum):
    TIMESTAMP = "timestamp"
    TRADE_ID = "trade_id"
    CLIENT = "client"
    SYMBOL = "symbol"
    QUANTITY = "quantity"
    PRICE = "price"
    VALUE = "value"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class TradeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trade_id: str = Field(examples=["BSE-20261110-000001"])
    client: str = Field(examples=["HDFC Mutual Fund"])
    symbol: str = Field(examples=["RELIANCE"])
    quantity: int = Field(gt=0, examples=[250])
    price: float = Field(gt=0, examples=[1314.55])
    trade_value: float = Field(gt=0, examples=[328637.50])
    timestamp: UTCDatetime
    source: str = Field(default="INITIAL_SEED", examples=["INITIAL_SEED", "BSE_PULL"])


class TradeSummary(BaseModel):
    total_trades: int = Field(ge=0)
    total_quantity: int = Field(ge=0)
    total_value: float = Field(ge=0.0)
    unique_clients: int = Field(ge=0)
    latest_trade_at: Optional[UTCDatetime] = None


class TradesResponse(BaseModel):
    items: List[TradeItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)
    summary: TradeSummary
    filtered_summary: TradeSummary


class TradeFiltersResponse(BaseModel):
    symbols: List[str]
    clients: List[str]
