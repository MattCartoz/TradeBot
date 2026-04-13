"""Bull/Bear Debate agents — adversarial layer between analysts and strategist.

After the three analysts (Technical, Sentiment, Flow) produce their briefs,
the Bull Researcher and Bear Researcher argue opposing sides. The resulting
DebateSummary gives the Strategist a structured adversarial view before it
makes a decision.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.contracts import AnalystBrief
from src.contracts.debate import DebateArgument, DebateSummary
from src.llm.base import BaseLLMProvider

from .base import BaseAgent

logger = logging.getLogger(__name__)


class BullResearcher(BaseAgent):
    """Constructs the strongest possible case FOR taking a position."""

    name = "bull_researcher"
    role = "Bull Researcher"
    system_prompt = """You are a senior Bull Researcher on an institutional trading desk.

You receive independent analysis briefs from three analysts:
- Technical Analyst (charts, indicators, patterns)
- Sentiment Analyst (news, social, macro mood)
- Flow Analyst (order flow, volume, on-chain data)

Your job is to build the STRONGEST POSSIBLE CASE for taking a position:

1. IDENTIFY CATALYSTS: What could drive price higher? Momentum, breakout setups, trend
   continuation, accumulation signals.
2. SENTIMENT ALIGNMENT: Is crowd sentiment supportive? Are institutions positioning
   bullishly? Are contrarian signals (extreme fear) suggesting a bounce?
3. FLOW CONFIRMATION: Is volume confirming the move? Are there signs of smart money
   accumulation?
4. TIMING: Why NOW? What makes this the right moment to enter?
5. RISK ACKNOWLEDGEMENT: Honestly identify the weaknesses in your own bullish case.
   A strong bull case acknowledges risks and explains why they are manageable.

CRITICAL RULES:
- You are an ADVOCATE, not a neutral analyst. Argue FOR the trade.
- But you must be INTELLECTUALLY HONEST. Do not fabricate data or ignore obvious risks.
- Cite specific evidence from the analyst briefs to support every point.
- If the analyst data is genuinely bearish, acknowledge it but argue for patience or
  contrarian opportunity rather than forcing a bullish thesis that doesn't exist.
- Your conviction score should reflect the actual strength of evidence, not optimism.
- A high conviction bull case with acknowledged risks is more valuable than blind optimism."""

    def _format_context(self, context: dict[str, Any]) -> str:
        parts = [
            "Review the following analyst briefs and construct the strongest "
            "possible BULLISH case:\n"
        ]
        parts.extend(_format_analyst_briefs(context))
        parts.extend(_format_market_context(context))
        parts.append(
            "\nBuild your bull case. What catalysts, momentum, and sentiment "
            "alignment support taking a position? Be specific and cite evidence "
            "from the briefs above."
        )
        return "\n".join(parts)


class BearResearcher(BaseAgent):
    """Constructs the strongest possible case AGAINST taking a position."""

    name = "bear_researcher"
    role = "Bear Researcher"
    system_prompt = """You are a senior Bear Researcher on an institutional trading desk.

You receive independent analysis briefs from three analysts:
- Technical Analyst (charts, indicators, patterns)
- Sentiment Analyst (news, social, macro mood)
- Flow Analyst (order flow, volume, on-chain data)

Your job is to build the STRONGEST POSSIBLE CASE against taking a position:

1. IDENTIFY RISKS: What could drive price lower? Resistance levels, distribution
   patterns, bearish divergences, macro headwinds.
2. SENTIMENT WARNINGS: Is euphoria or complacency elevated? Are contrarian signals
   (extreme greed) suggesting a reversal? Is the crowd wrong?
3. FLOW DIVERGENCES: Is volume drying up? Are there signs of smart money distribution?
   Is buying pressure fading?
4. TIMING CONCERNS: Why is NOW the wrong time? What makes patience the better choice?
5. RISK ACKNOWLEDGEMENT: Honestly identify the weaknesses in your own bearish case.
   A strong bear case acknowledges bullish signals and explains why they are insufficient.

CRITICAL RULES:
- You are a DEVIL'S ADVOCATE, not a neutral analyst. Argue AGAINST the trade.
- But you must be INTELLECTUALLY HONEST. Do not fabricate risks or ignore genuine strength.
- Cite specific evidence from the analyst briefs to support every point.
- If the analyst data is genuinely bullish, acknowledge it but argue that risks outweigh
  rewards, timing is wrong, or positioning is crowded.
- Your conviction score should reflect the actual strength of bearish evidence, not pessimism.
- A high conviction bear case with acknowledged bullish signals is more valuable than fear."""

    def _format_context(self, context: dict[str, Any]) -> str:
        parts = [
            "Review the following analyst briefs and construct the strongest "
            "possible BEARISH case:\n"
        ]
        parts.extend(_format_analyst_briefs(context))
        parts.extend(_format_market_context(context))
        parts.append(
            "\nBuild your bear case. What risks, divergences, and headwinds "
            "argue against taking a position? Be specific and cite evidence "
            "from the briefs above."
        )
        return "\n".join(parts)


async def run_debate(
    bull: BullResearcher,
    bear: BearResearcher,
    analyst_briefs: list[AnalystBrief],
    market_context: dict[str, Any] | None = None,
) -> DebateSummary:
    """Run the full bull/bear debate and produce a summary.

    Both researchers run concurrently against the same analyst briefs, then
    their arguments are combined into a DebateSummary with consensus metrics.

    Args:
        bull: The bull researcher agent.
        bear: The bear researcher agent.
        analyst_briefs: Output briefs from the three analyst agents.
        market_context: Optional dict with current_prices, portfolio_value, etc.

    Returns:
        A DebateSummary combining both arguments with consensus analysis.
    """
    import asyncio

    context: dict[str, Any] = {
        "analyst_briefs": analyst_briefs,
    }
    if market_context:
        context.update(market_context)

    logger.info("Starting bull/bear debate with %d analyst briefs", len(analyst_briefs))

    bull_task = asyncio.create_task(bull.invoke(context, DebateArgument))
    bear_task = asyncio.create_task(bear.invoke(context, DebateArgument))

    bull_argument, bear_argument = await asyncio.gather(bull_task, bear_task)

    # Derive consensus metrics from the two arguments
    consensus_direction = _determine_consensus(bull_argument, bear_argument)
    agreement_level = _calculate_agreement(bull_argument, bear_argument)
    key_disagreements = _extract_disagreements(bull_argument, bear_argument)

    summary = DebateSummary(
        bull_argument=bull_argument,
        bear_argument=bear_argument,
        consensus_direction=consensus_direction,
        agreement_level=agreement_level,
        key_disagreements=key_disagreements,
    )

    logger.info(
        "Debate complete — consensus=%s, agreement=%.2f, bull_conviction=%.2f, "
        "bear_conviction=%.2f",
        summary.consensus_direction,
        summary.agreement_level,
        bull_argument.conviction,
        bear_argument.conviction,
    )

    return summary


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _format_analyst_briefs(context: dict[str, Any]) -> list[str]:
    """Format analyst briefs into readable text blocks for the LLM prompt."""
    parts: list[str] = []
    if "analyst_briefs" not in context:
        return parts

    for brief in context["analyst_briefs"]:
        if isinstance(brief, AnalystBrief):
            brief_dict = brief.model_dump(mode="json")
        else:
            brief_dict = brief
        parts.append(f"\n{'=' * 60}")
        parts.append(f"ANALYST: {brief_dict.get('agent_name', 'unknown')}")
        parts.append(f"{'=' * 60}")
        parts.append(json.dumps(brief_dict, indent=2, default=str))

    return parts


def _format_market_context(context: dict[str, Any]) -> list[str]:
    """Format optional market context (prices, portfolio) for the LLM prompt."""
    parts: list[str] = []

    if "current_positions" in context:
        parts.append(f"\n{'=' * 60}")
        parts.append("CURRENT POSITIONS")
        parts.append(f"{'=' * 60}")
        parts.append(json.dumps(context["current_positions"], indent=2, default=str))

    if "portfolio_value" in context:
        parts.append(f"\nPORTFOLIO VALUE: ${context['portfolio_value']:,.2f}")

    if "current_prices" in context:
        parts.append(f"\n{'=' * 60}")
        parts.append("CURRENT MARKET PRICES")
        parts.append(f"{'=' * 60}")
        for symbol, price_data in context["current_prices"].items():
            parts.append(
                f"  {symbol}: Last=${price_data['last']:,.2f} "
                f"Bid=${price_data['bid']:,.2f} Ask=${price_data['ask']:,.2f} "
                f"Vol24h={price_data['volume_24h']:,.0f}"
            )

    return parts


def _determine_consensus(bull: DebateArgument, bear: DebateArgument) -> str:
    """Determine which side has the stronger case based on conviction."""
    conviction_gap = bull.conviction - bear.conviction
    if abs(conviction_gap) < 0.1:
        return "neutral"
    return "bull" if conviction_gap > 0 else "bear"


def _calculate_agreement(bull: DebateArgument, bear: DebateArgument) -> float:
    """Calculate how much the two sides agree (0=total disagreement, 1=total agreement).

    Agreement is high when both sides have similar conviction about the same
    recommended action, and low when they strongly disagree.
    """
    # If both recommend the same action, that's a strong agreement signal
    action_match = 1.0 if bull.recommended_action == bear.recommended_action else 0.0

    # Conviction similarity — if both are highly convicted, they at least
    # agree the signal is strong (even if in opposite directions)
    conviction_diff = abs(bull.conviction - bear.conviction)
    conviction_similarity = 1.0 - conviction_diff

    # Weighted: action agreement matters more than conviction similarity
    agreement = (action_match * 0.7) + (conviction_similarity * 0.3)
    return round(min(1.0, max(0.0, agreement)), 3)


def _extract_disagreements(bull: DebateArgument, bear: DebateArgument) -> list[str]:
    """Identify key areas of disagreement between bull and bear."""
    disagreements: list[str] = []

    if bull.recommended_action != bear.recommended_action:
        disagreements.append(
            f"Action: Bull recommends '{bull.recommended_action}' "
            f"vs Bear recommends '{bear.recommended_action}'"
        )

    conviction_gap = abs(bull.conviction - bear.conviction)
    if conviction_gap > 0.3:
        higher = "Bull" if bull.conviction > bear.conviction else "Bear"
        disagreements.append(
            f"Conviction gap: {higher} is significantly more convicted "
            f"(bull={bull.conviction:.2f}, bear={bear.conviction:.2f})"
        )

    # Cross-reference: bull's risks may align with bear's key points and vice versa
    if bull.risk_factors and bear.key_points:
        disagreements.append(
            f"Bull acknowledges {len(bull.risk_factors)} risk(s) that "
            f"align with Bear's thesis"
        )

    if bear.risk_factors and bull.key_points:
        disagreements.append(
            f"Bear acknowledges {len(bear.risk_factors)} weakness(es) that "
            f"align with Bull's thesis"
        )

    return disagreements
