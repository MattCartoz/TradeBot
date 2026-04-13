"""Alpaca paper trading integration — real market data, simulated fills."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

from src.contracts import ExecutionOrder, FillReport, OrderSide, OrderStatus, OrderType

from .base import BaseExchange

logger = logging.getLogger(__name__)


class AlpacaPaperExchange(BaseExchange):
    """Alpaca paper trading — real market data, zero risk."""

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        paper: bool = True,
    ):
        self._api_key = api_key or os.environ.get("ALPACA_API_KEY", "")
        self._secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY", "")
        self._paper = paper
        self._client: TradingClient | None = None

    async def initialize(self) -> None:
        self._client = TradingClient(
            api_key=self._api_key,
            secret_key=self._secret_key,
            paper=self._paper,
        )
        account = self._client.get_account()
        logger.info(
            "Alpaca paper account initialized: $%s portfolio value",
            account.portfolio_value,
        )

    async def get_balance(self) -> dict[str, float]:
        assert self._client is not None
        account = self._client.get_account()
        return {
            "USD": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
        }

    async def get_portfolio_value(self) -> float:
        assert self._client is not None
        account = self._client.get_account()
        return float(account.portfolio_value)

    async def get_positions(self) -> list[dict]:
        assert self._client is not None
        positions = self._client.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "side": "long" if float(p.qty) > 0 else "short",
                "quantity": abs(float(p.qty)),
                "entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "unrealized_pnl": float(p.unrealized_pl),
                "unrealized_pnl_pct": float(p.unrealized_plpc) * 100,
                "market_value": float(p.market_value),
            }
            for p in positions
        ]

    async def submit_order(self, order: ExecutionOrder) -> FillReport:
        assert self._client is not None

        alpaca_side = AlpacaSide.BUY if order.side == OrderSide.BUY else AlpacaSide.SELL
        symbol = order.symbol.replace("/", "")  # BTC/USD -> BTCUSD

        try:
            if order.order_type == OrderType.MARKET:
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=order.quantity,
                    side=alpaca_side,
                    time_in_force=TimeInForce.GTC,
                )
            else:
                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=order.quantity,
                    side=alpaca_side,
                    time_in_force=TimeInForce.GTC,
                    limit_price=order.limit_price,
                )

            alpaca_order = self._client.submit_order(request)

            return FillReport(
                order_id=str(uuid.uuid4()),
                symbol=order.symbol,
                side=order.side,
                status=OrderStatus.FILLED,
                requested_quantity=order.quantity,
                filled_quantity=float(alpaca_order.filled_qty or order.quantity),
                average_fill_price=float(
                    alpaca_order.filled_avg_price or order.limit_price or 0
                ),
                slippage_pct=0.0,
                exchange_order_id=str(alpaca_order.id),
            )

        except Exception as e:
            logger.error("Order submission failed: %s", e)
            return FillReport(
                order_id=str(uuid.uuid4()),
                symbol=order.symbol,
                side=order.side,
                status=OrderStatus.REJECTED,
                requested_quantity=order.quantity,
                filled_quantity=0.0,
                average_fill_price=0.0,
                slippage_pct=0.0,
            )

    async def cancel_order(self, order_id: str) -> bool:
        assert self._client is not None
        try:
            self._client.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            logger.error("Failed to cancel order %s: %s", order_id, e)
            return False

    async def close(self) -> None:
        self._client = None
