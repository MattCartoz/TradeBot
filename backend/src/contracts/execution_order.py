"""Structured contracts for order execution and fill reports."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class ExecutionOrder(BaseModel):
    """Order to be sent to the exchange by the Executor agent."""

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float = Field(gt=0)
    limit_price: float | None = None
    stop_price: float | None = None
    take_profit: float | None = None
    stop_loss: float | None = None
    time_in_force: str = "gtc"


class FillReport(BaseModel):
    """Report from the exchange after an order is executed."""

    order_id: str
    symbol: str
    side: OrderSide
    status: OrderStatus
    requested_quantity: float
    filled_quantity: float
    average_fill_price: float
    slippage_pct: float = Field(description="Actual vs expected price difference %")
    fees: float = 0.0
    filled_at: datetime = Field(default_factory=datetime.utcnow)
    exchange_order_id: str | None = None
