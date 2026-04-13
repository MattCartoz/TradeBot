"""Strategist agent — reads all analyst briefs, classifies regime, selects strategy."""

from __future__ import annotations

import json
from typing import Any

from src.contracts import AnalystBrief, StrategyDecision

from .base import BaseAgent


class Strategist(BaseAgent):
    name = "strategist"
    role = "Strategist"
    system_prompt = """You are the Chief Strategist on an institutional trading desk.

You receive independent analysis briefs from three analysts:
- Technical Analyst (charts, indicators, patterns)
- Sentiment Analyst (news, social, macro mood)
- Flow Analyst (order flow, volume, on-chain data)

Your job:
1. CLASSIFY THE MARKET REGIME: trending_up, trending_down, ranging, volatile, or dead
2. ASSESS ANALYST AGREEMENT: Do the analysts agree? Where do they diverge?
3. SELECT A STRATEGY from the playbook appropriate to the current regime
4. PROPOSE AN ACTION: buy, sell, hold, or close — with specific entry, target, and stop
5. ASSIGN A CONVICTION SCORE (0.0 to 1.0): How confident are you?

CRITICAL RULES:
- The DEFAULT action is HOLD. You must have compelling evidence to recommend a trade.
- Analyst disagreement LOWERS conviction. Agreement raises it.
- Never propose a trade without a stop-loss. Always define the exit before the entry.
- Consider the playbook — what strategies have worked in this regime before?
- A conviction score below the threshold means the trade won't happen. Be honest.
- Risk/reward must be at least 2:1. If the math doesn't work, HOLD.
- You CANNOT override the Risk Manager. If your trade gets vetoed, accept it.
- Document your reasoning thoroughly — this is your audit trail."""

    def _format_context(self, context: dict[str, Any]) -> str:
        parts = ["Review the following analyst briefs and make a strategic decision:\n"]

        if "analyst_briefs" in context:
            for brief in context["analyst_briefs"]:
                if isinstance(brief, AnalystBrief):
                    brief_dict = brief.model_dump(mode="json")
                else:
                    brief_dict = brief
                parts.append(f"\n{'='*60}")
                parts.append(f"ANALYST: {brief_dict.get('agent_name', 'unknown')}")
                parts.append(f"{'='*60}")
                parts.append(json.dumps(brief_dict, indent=2, default=str))

        if "playbook" in context:
            parts.append(f"\n{'='*60}")
            parts.append("STRATEGY PLAYBOOK")
            parts.append(f"{'='*60}")
            parts.append(json.dumps(context["playbook"], indent=2, default=str))

        if "current_positions" in context:
            parts.append(f"\nCURRENT POSITIONS:\n")
            parts.append(json.dumps(context["current_positions"], indent=2, default=str))

        if "portfolio_value" in context:
            parts.append(f"\nPORTFOLIO VALUE: ${context['portfolio_value']:,.2f}")

        parts.append(
            "\nBased on all analyst briefs and the playbook, what is your strategic decision? "
            "Remember: the default is HOLD. Only propose a trade if conviction is high."
        )

        return "\n".join(parts)
