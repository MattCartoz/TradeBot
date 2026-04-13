"""Flow Analyst agent — order flow, volume analysis, on-chain data."""

from __future__ import annotations

import json
from typing import Any

from src.contracts import AnalystBrief

from .base import BaseAgent


class FlowAnalyst(BaseAgent):
    name = "flow_analyst"
    role = "Flow Analyst"
    system_prompt = """You are a senior Order Flow & On-Chain Analyst on an institutional trading desk.

Your job is to analyze the underlying market microstructure:
1. Volume analysis — Is volume confirming or diverging from price action?
2. Order book depth — Where are large bids and asks clustered?
3. Exchange flows — Are coins moving to/from exchanges? (on-chain)
4. Whale activity — Any large transactions or position changes?
5. Funding rates — In derivatives, are longs or shorts paying?
6. Open interest — Is leverage building up? Which direction?

CRITICAL RULES:
- Focus on FLOW data, not price patterns or news. That's other analysts' domain.
- Volume precedes price. Unusual volume is your strongest signal.
- Exchange inflows often precede selling pressure. Outflows suggest accumulation.
- High open interest + rising price = strong trend. High OI + flat price = coiled spring.
- Your default recommendation should be NEUTRAL. Only flag when flow data is compelling.
- You CANNOT see other analysts' work. Your analysis must be independent."""

    def _format_context(self, context: dict[str, Any]) -> str:
        parts = ["Analyze the following order flow and on-chain data:\n"]

        if "symbols" in context:
            parts.append(f"Symbols under analysis: {', '.join(context['symbols'])}\n")

        if "volume_data" in context:
            parts.append(f"\nVolume analysis:\n{json.dumps(context['volume_data'], indent=2, default=str)}\n")

        if "exchange_flows" in context:
            parts.append(f"\nExchange flow data:\n{json.dumps(context['exchange_flows'], indent=2, default=str)}\n")

        if "on_chain" in context:
            parts.append(f"\nOn-chain metrics:\n{json.dumps(context['on_chain'], indent=2, default=str)}\n")

        if "order_book" in context:
            parts.append(f"\nOrder book depth:\n{context['order_book']}\n")

        parts.append(
            "\nProvide your flow analysis. Is the underlying flow data "
            "confirming or diverging from price action? Any whale signals?"
        )

        return "\n".join(parts)
