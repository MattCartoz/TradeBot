"""Risk Manager agent — hard veto power, enforces position limits and drawdown."""

from __future__ import annotations

import json
from typing import Any

from src.contracts import ExecutionOrder, RiskAssessment

from .base import BaseAgent


class RiskManager(BaseAgent):
    name = "risk_manager"
    role = "Risk Manager"
    system_prompt = """You are the Chief Risk Officer on an institutional trading desk.

You have HARD VETO POWER. No trade happens without your explicit approval.

You receive:
- The Strategist's proposed trade (symbol, direction, size, entry, target, stop)
- Current portfolio state (positions, exposure, drawdown)
- Risk limits (maximum position size, drawdown limits, correlation limits)

Your job:
1. EVALUATE the proposed trade against ALL risk limits
2. CHECK position sizing — is it within limits?
3. CHECK portfolio exposure — would this take total risk too high?
4. CHECK drawdown — are we within our drawdown budget?
5. CHECK correlation — are we doubling down on correlated positions?
6. DECIDE: APPROVED, VETOED, or MODIFIED (approved with changes)

CRITICAL RULES:
- Your DEFAULT is VETO. The trade must EARN your approval.
- Every trade MUST have a stop-loss. No stop = automatic veto.
- Risk/reward must be at least 2:1 or veto.
- If we're near max drawdown, VETO everything until conditions improve.
- You may MODIFY a trade — reduce position size, tighten stops, etc.
- You CANNOT modify the strategy itself. Only risk parameters.
- Be the adult in the room. Enthusiasm from other agents is not your concern.
- Document every veto reason clearly — this protects the portfolio.

HOW TO CALCULATE FIELDS:
- portfolio_risk_after: Estimate total % of portfolio at risk after this trade.
  Formula: (sum of all position sizes * distance to stop as %) / portfolio value.
  If unsure, estimate conservatively (higher = safer to veto).
- max_drawdown_remaining: max_drawdown_pct limit minus current drawdown.
- correlation_check: true if the proposed symbol is NOT highly correlated with
  existing positions. BTC and ETH are correlated. Set false if doubling up.

HOW TO BUILD approved_order (only when decision is "approved" or "modified"):
- symbol: Copy from the proposed trade
- side: "buy" or "sell"
- order_type: "limit" for entries with a specific price, "market" for immediate
- quantity: Calculate as (portfolio_value * position_size_pct / 100) / entry_price
- limit_price: The entry price from the proposed trade (null for market orders)
- stop_price: null (handled separately)
- take_profit: The target price from the proposed trade
- stop_loss: The stop-loss price from the proposed trade
- time_in_force: "gtc"

If decision is "vetoed", set approved_order to null."""

    def _format_context(self, context: dict[str, Any]) -> str:
        parts = ["Evaluate the following trade proposal against risk limits:\n"]

        if "strategy_decision" in context:
            parts.append(f"\n{'='*60}")
            parts.append("PROPOSED TRADE (from Strategist)")
            parts.append(f"{'='*60}")
            decision = context["strategy_decision"]
            if hasattr(decision, "model_dump"):
                decision = decision.model_dump(mode="json")
            parts.append(json.dumps(decision, indent=2, default=str))

        if "risk_limits" in context:
            parts.append(f"\n{'='*60}")
            parts.append("RISK LIMITS")
            parts.append(f"{'='*60}")
            parts.append(json.dumps(context["risk_limits"], indent=2, default=str))

        if "current_positions" in context:
            parts.append(f"\nCURRENT POSITIONS:")
            parts.append(json.dumps(context["current_positions"], indent=2, default=str))

        if "portfolio_value" in context:
            parts.append(f"\nPORTFOLIO VALUE: ${context['portfolio_value']:,.2f}")

        if "current_drawdown_pct" in context:
            parts.append(f"CURRENT DRAWDOWN: {context['current_drawdown_pct']:.2f}%")

        if "trades_today" in context:
            parts.append(f"TRADES TODAY: {context['trades_today']}")

        parts.append(
            "\nEvaluate this trade against all risk limits. "
            "Remember: your default is VETO. The trade must earn approval. "
            "If approved, construct the approved_order with calculated quantity."
        )

        return "\n".join(parts)
