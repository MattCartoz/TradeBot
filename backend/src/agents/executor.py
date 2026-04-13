"""Executor agent — the ONLY agent that touches the exchange API."""

from __future__ import annotations

import logging
from typing import Any

from src.contracts import ExecutionOrder, FillReport, OrderSide, OrderType, RiskAssessment
from src.exchange.base import BaseExchange

logger = logging.getLogger(__name__)


class Executor:
    """Executor — translates approved orders into exchange API calls.

    This is NOT an LLM agent. Order execution is deterministic:
    the Risk Manager already approved the exact order parameters.
    The Executor handles order type selection and slippage management.
    """

    name = "executor"
    role = "Executor"

    def __init__(self, exchange: BaseExchange):
        self.exchange = exchange

    async def execute(self, risk_assessment: RiskAssessment) -> FillReport | None:
        """Execute an approved order.

        Only processes orders that the Risk Manager has explicitly approved.
        """
        if risk_assessment.approved_order is None:
            logger.warning("[Executor] No approved order to execute")
            return None

        order = risk_assessment.approved_order
        logger.info(
            "[Executor] Submitting %s %s %s qty=%.6f",
            order.order_type.value,
            order.side.value,
            order.symbol,
            order.quantity,
        )

        fill = await self.exchange.submit_order(order)

        logger.info(
            "[Executor] %s — filled %.6f @ $%.2f (slippage: %.3f%%)",
            fill.status.value,
            fill.filled_quantity,
            fill.average_fill_price,
            fill.slippage_pct,
        )

        return fill
