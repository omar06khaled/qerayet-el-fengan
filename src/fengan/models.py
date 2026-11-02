"""Broker-neutral data models. The MCP tools only ever see these, never raw SDK objects."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"  # conditional: triggers when price crosses stop_price


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Account(BaseModel):
    account_id: str
    currency: str = "EGP"
    cash: float
    equity: float
    buying_power: float


class Position(BaseModel):
    symbol: str
    quantity: int
    avg_cost: float
    last_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class Quote(BaseModel):
    symbol: str
    name: str
    last: float
    change_pct: float
    volume: int
    as_of: datetime


class Bar(BaseModel):
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class OrderRequest(BaseModel):
    symbol: str
    side: Side
    quantity: int = Field(gt=0)
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = Field(default=None, gt=0)
    stop_price: Optional[float] = Field(default=None, gt=0)


class Order(BaseModel):
    order_id: str
    request: OrderRequest
    status: OrderStatus
    created_at: datetime
    filled_price: Optional[float] = None
