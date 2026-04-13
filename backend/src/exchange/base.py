"""Base exchange interface — abstraction over paper and live trading."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.contracts import ExecutionOrder, FillReport


class BaseExchange(ABC):
    """Interface that all exchange connectors must implement."""

    @abstractmethod
    async def initialize(self) -> None:
        """Set up the exchange connection."""

    @abstractmethod
    async def get_balance(self) -> dict[str, float]:
        """Get account balances. Returns {'USD': 100000, 'BTC': 0.5, ...}."""

    @abstractmethod
    async def get_portfolio_value(self) -> float:
        """Get total portfolio value in USD."""

    @abstractmethod
    async def get_positions(self) -> list[dict]:
        """Get all open positions."""

    @abstractmethod
    async def submit_order(self, order: ExecutionOrder) -> FillReport:
        """Submit an order and return the fill report."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order. Returns True if successful."""

    @abstractmethod
    async def get_open_orders(self) -> list[dict]:
        """Return all pending/open orders."""

    @abstractmethod
    async def cancel_stale_orders(self, max_age_minutes: int = 30) -> list[str]:
        """Cancel orders older than *max_age_minutes*. Returns cancelled order IDs."""

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
