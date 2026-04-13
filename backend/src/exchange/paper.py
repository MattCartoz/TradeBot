"""Alpaca paper trading integration — real market data, simulated fills."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

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
        if self._client is None:
            raise RuntimeError("Exchange not initialized. Call initialize() first.")
        account = self._client.get_account()
        return {
            "USD": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
        }

    async def get_portfolio_value(self) -> float:
        if self._client is None:
            raise RuntimeError("Exchange not initialized. Call initialize() first.")
        account = self._client.get_account()
        return float(account.portfolio_value)

    async def get_positions(self) -> list[dict]:
        if self._client is None:
            raise RuntimeError("Exchange not initialized. Call initialize() first.")
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
        if self._client is None:
            raise RuntimeError("Exchange not initialized. Call initialize() first.")

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
        if self._client is None:
            raise RuntimeError("Exchange not initialized. Call initialize() first.")
        try:
            self._client.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            logger.error("Failed to cancel order %s: %s", order_id, e)
            return False

    async def get_open_orders(self) -> list[dict]:
        """Return all pending/open orders from Alpaca."""
        if self._client is None:
            raise RuntimeError("Exchange not initialized. Call initialize() first.")
        try:
            orders = self._client.get_orders(
                filter={"status": "open"}
            )
            return [
                {
                    "order_id": str(o.id),
                    "symbol": o.symbol,
                    "side": str(o.side),
                    "type": str(o.type),
                    "quantity": float(o.qty),
                    "limit_price": float(o.limit_price) if o.limit_price else None,
                    "status": str(o.status),
                    "created_at": o.created_at,
                }
                for o in orders
            ]
        except Exception as e:
            logger.error("Failed to fetch open orders: %s", e)
            return []

    async def cancel_stale_orders(self, max_age_minutes: int = 30) -> list[str]:
        """Cancel open orders older than *max_age_minutes*.

        Returns a list of order IDs that were successfully cancelled.
        """
        if self._client is None:
            raise RuntimeError("Exchange not initialized. Call initialize() first.")

        open_orders = await self.get_open_orders()
        cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=max_age_minutes)
        cancelled: list[str] = []

        for order in open_orders:
            created_at = order["created_at"]
            # Ensure the timestamp is timezone-aware for comparison
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            if created_at < cutoff:
                order_id = order["order_id"]
                if await self.cancel_order(order_id):
                    cancelled.append(order_id)
                    logger.info(
                        "Cancelled stale order %s (age: %s)",
                        order_id,
                        datetime.now(tz=timezone.utc) - created_at,
                    )

        if cancelled:
            logger.info("Cancelled %d stale order(s)", len(cancelled))
        return cancelled

    async def close(self) -> None:
        self._client = None
