"""Auditor agent — post-trade review, post-mortem analysis, playbook evolution.

The Auditor is the system's learning engine. After every closed trade,
it reviews what happened, why, and what should change.
"""

from __future__ import annotations

import json
from typing import Any

from src.contracts import TradePostMortem

from .base import BaseAgent


class Auditor(BaseAgent):
    name = "auditor"
    role = "Auditor"
    system_prompt = """You are the Chief Auditor on an institutional trading desk.

After every closed trade, you conduct a thorough post-mortem analysis.

You receive:
- The original analyst briefs that led to the trade
- The Strategist's decision and reasoning
- The Risk Manager's assessment
- The actual trade execution details
- The outcome (P&L, duration, price path)

Your job:
1. EVALUATE the trade outcome — win, loss, or breakeven
2. ASSESS what went right and what went wrong
3. EVALUATE PATTERN ACCURACY — was the technical analysis correct?
4. EVALUATE REGIME ACCURACY — was the market regime classified correctly?
5. DERIVE LESSONS — what can the system learn from this trade?
6. RECOMMEND PLAYBOOK UPDATES — should any strategies be adjusted?

CRITICAL RULES:
- Be brutally honest. Don't sugarcoat losses or over-celebrate wins.
- A winning trade with bad reasoning is WORSE than a losing trade with good reasoning.
- Focus on PROCESS, not outcome. Sometimes good trades lose.
- Look for systematic patterns — are we consistently wrong about certain setups?
- Playbook updates should be specific and actionable, not vague.
- Your recommendations evolve the system over time. This is the real edge.
- You CANNOT modify risk limits. Only recommend strategy changes."""

    def _format_context(self, context: dict[str, Any]) -> str:
        parts = ["Conduct a post-mortem analysis of the following closed trade:\n"]

        if "trade_data" in context:
            parts.append(f"\n{'='*60}")
            parts.append("TRADE DETAILS")
            parts.append(f"{'='*60}")
            parts.append(json.dumps(context["trade_data"], indent=2, default=str))

        if "analyst_briefs" in context:
            parts.append(f"\n{'='*60}")
            parts.append("ANALYST BRIEFS AT ENTRY")
            parts.append(f"{'='*60}")
            parts.append(json.dumps(context["analyst_briefs"], indent=2, default=str))

        if "strategy_decision" in context:
            parts.append(f"\n{'='*60}")
            parts.append("STRATEGIST DECISION")
            parts.append(f"{'='*60}")
            parts.append(json.dumps(context["strategy_decision"], indent=2, default=str))

        if "risk_assessment" in context:
            parts.append(f"\n{'='*60}")
            parts.append("RISK ASSESSMENT")
            parts.append(f"{'='*60}")
            parts.append(json.dumps(context["risk_assessment"], indent=2, default=str))

        if "playbook" in context:
            parts.append(f"\n{'='*60}")
            parts.append("CURRENT PLAYBOOK")
            parts.append(f"{'='*60}")
            parts.append(json.dumps(context["playbook"], indent=2, default=str))

        parts.append(
            "\nConduct your post-mortem. Be thorough and honest. "
            "Focus on process over outcome. Recommend specific playbook updates."
        )

        return "\n".join(parts)
