"""Position Manager agent — AI-driven management of all open positions every cycle.

This is the critical difference between this system and hardcoded bots: instead of
fixed trailing stop percentages and ROI tables, the AI dynamically evaluates each
open position and decides whether to hold, adjust stops, take partial profit, or close.
"""

from __future__ import annotations

import json
from typing import Any

from src.contracts import PositionManagerOutput, PositionReview

from .base import BaseAgent


class PositionManager(BaseAgent):
    name = "position_manager"
    role = "Position Manager"
    system_prompt = """You are the Position Manager on an institutional trading desk.

You run EVERY cycle and review EVERY open position. Your job is to dynamically manage
positions using judgment — NOT hardcoded rules. This is what separates an AI-driven
desk from a dumb bot with fixed trailing stops and ROI tables.

You receive for each position:
- Entry price, current price, unrealized P&L
- Current stop-loss and take-profit levels
- How long the position has been open
- The original entry reasoning (why was this trade taken?)
- Current market indicators (RSI, MACD, ATR, moving averages, volume)
- Current market regime (trending_up, trending_down, ranging, volatile, dead)

For each position, decide one of:
- HOLD: Keep the position as-is. This is the DEFAULT. Only change when there's a reason.
- ADJUST_STOP: Move the stop-loss. Provide the new stop-loss price.
- TAKE_PARTIAL: Sell a fraction of the position. Provide partial_close_pct (0.0-1.0).
- CLOSE: Exit the entire position immediately.

TRAILING STOP BEHAVIOR (AI-driven, not a fixed percentage):
- In a strong uptrend with momentum confirmed, MOVE STOPS UP to lock in profit.
  How far behind price? That depends on volatility:
  - High ATR = give the position room to breathe. Wider trailing distance.
  - Low ATR = tighten the stop. The position doesn't need as much room.
- In a downtrend (for short positions), move stops DOWN to lock in profit.
- Never move a stop BACKWARDS (further from current price / increasing risk).
  Stops only ratchet in the direction of profit.

PARTIAL PROFIT TAKING:
- When a position has reached significant unrealized profit (e.g., 2x or 3x the
  original risk), consider taking some off the table — especially if momentum shows
  signs of fading.
- Partial closes protect against giving back all gains while still allowing the
  remaining position to capture further upside.
- Typical partial sizes: 25%, 33%, or 50%. Choose based on conviction in continuation.

THESIS INVALIDATION:
- Every position was opened for a reason (the entry reasoning). If the conditions
  that justified the entry NO LONGER HOLD, exit regardless of P&L.
- Examples: regime changed from trending to ranging, key support/resistance broken
  against the position, volume dried up, a catalyst that was expected didn't materialize.
- A position that is in profit but whose thesis is broken should still be closed.
  Don't let P&L blind you to changed conditions.

TIME DECAY:
- Positions that have been open for a long time with no meaningful movement are
  tying up capital. Review them for exit.
- "Long time" is relative — in crypto a day can be too long in high volatility,
  or a week might be fine in a slow grind.
- Flat positions in a dead regime are the clearest candidates for time-based exit.

URGENCY:
- Set urgency 0.0–1.0 to indicate how quickly the action should be executed.
- 0.0: No rush, next cycle is fine (routine stop adjustment).
- 0.5: Should act this cycle (momentum fading, approaching key level).
- 1.0: Immediate action required (thesis broken, sudden regime shift, gap risk).

CRITICAL RULES:
- The DEFAULT is HOLD. Do not churn positions. Only act when there is a clear reason.
- Every review MUST include reasoning — this is the audit trail.
- Always set thesis_still_valid honestly. A position can be HOLD with thesis invalid
  (if you're setting urgency high for next-cycle close), but generally invalid thesis
  means CLOSE.
- When adjusting stops, always provide the exact new_stop_loss price.
- When taking partial, always provide partial_close_pct between 0.0 and 1.0.
- You MUST return one review per open position. Do not skip any."""

    def _format_context(self, context: dict[str, Any]) -> str:
        parts = ["Review all open positions and decide actions for each:\n"]

        if "market_regime" in context:
            parts.append(f"CURRENT MARKET REGIME: {context['market_regime']}")

        if "regime_confidence" in context:
            parts.append(f"REGIME CONFIDENCE: {context['regime_confidence']:.2f}")

        if "portfolio_value" in context:
            parts.append(f"PORTFOLIO VALUE: ${context['portfolio_value']:,.2f}")

        # --- Open positions (the core input) ---
        if "positions" in context:
            parts.append(f"\n{'='*60}")
            parts.append("OPEN POSITIONS")
            parts.append(f"{'='*60}")
            for i, pos in enumerate(context["positions"], 1):
                if hasattr(pos, "model_dump"):
                    pos = pos.model_dump(mode="json")
                parts.append(f"\n--- Position #{i} ---")
                parts.append(json.dumps(pos, indent=2, default=str))

        # --- Current market prices ---
        if "current_prices" in context:
            parts.append(f"\n{'='*60}")
            parts.append("CURRENT MARKET PRICES")
            parts.append(f"{'='*60}")
            for symbol, price_data in context["current_prices"].items():
                if isinstance(price_data, dict):
                    parts.append(f"  {symbol}: {json.dumps(price_data, default=str)}")
                else:
                    parts.append(f"  {symbol}: {price_data}")

        # --- Technical indicators ---
        if "indicators" in context:
            parts.append(f"\n{'='*60}")
            parts.append("TECHNICAL INDICATORS")
            parts.append(f"{'='*60}")
            for symbol, ind in context["indicators"].items():
                parts.append(f"\n  {symbol}:")
                if isinstance(ind, dict):
                    for key, val in ind.items():
                        parts.append(f"    {key}: {val}")
                else:
                    parts.append(f"    {ind}")

        # --- Original entry reasoning for each position ---
        if "entry_reasoning" in context:
            parts.append(f"\n{'='*60}")
            parts.append("ORIGINAL ENTRY REASONING")
            parts.append(f"{'='*60}")
            for symbol, reasoning in context["entry_reasoning"].items():
                parts.append(f"\n  {symbol}: {reasoning}")

        parts.append(
            "\nReview each open position above and return a decision for each. "
            "Remember: the default is HOLD. Only adjust when there is a clear reason. "
            "Never move a stop backwards. Consider regime, volatility, thesis validity, "
            "and time held."
        )

        return "\n".join(parts)

    async def review_positions(
        self, context: dict[str, Any]
    ) -> PositionManagerOutput:
        """Convenience method: invoke the agent and return typed output.

        This is the primary entry point for the orchestrator to call each cycle.

        Args:
            context: Must include at minimum:
                - positions: list of open position dicts/models
                - current_prices: dict mapping symbol to price data
                - indicators: dict mapping symbol to indicator values
                - market_regime: current regime string
                Optional but recommended:
                - entry_reasoning: dict mapping symbol to original thesis
                - portfolio_value: float
                - regime_confidence: float

        Returns:
            PositionManagerOutput with one PositionReview per open position.
        """
        return await self.invoke(context, PositionManagerOutput)
