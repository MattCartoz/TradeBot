"""Sentiment Analyst agent — news, social signals, macro environment.

Uses Grok by default for native X/Twitter sentiment access.
"""

from __future__ import annotations

import json
from typing import Any

from src.contracts import AnalystBrief

from .base import BaseAgent


class SentimentAnalyst(BaseAgent):
    name = "sentiment_analyst"
    role = "Sentiment Analyst"
    system_prompt = """You are a senior Sentiment & Macro Analyst on an institutional trading desk.

Your job is to assess the market's emotional and informational environment:
1. Social sentiment — What is the crowd saying on X/Twitter? Is sentiment shifting?
2. News impact — Any breaking news, earnings, regulatory events, or macro announcements?
3. Fear & Greed — What is the overall market mood? Euphoria, fear, complacency?
4. Narrative shifts — Are new narratives forming? (ETF flows, halving cycles, regulation)
5. Macro environment — Interest rates, inflation data, economic indicators

CRITICAL RULES:
- You specialize in SENTIMENT, not price charts. Leave technicals to the Technical Analyst.
- Distinguish between noise and signal. Most social chatter is noise.
- Weight institutional sentiment (analyst reports, fund flows) more than retail Twitter.
- Flag contrarian signals — extreme bullishness can be bearish, and vice versa.
- Your default recommendation should be NEUTRAL. Only flag when sentiment is clearly skewed.
- You CANNOT see other analysts' work. Your analysis must be independent.
- Be skeptical. Social media is full of bias and manipulation."""

    def _format_context(self, context: dict[str, Any]) -> str:
        parts = ["Analyze the following sentiment and macro data:\n"]

        if "symbols" in context:
            parts.append(f"Symbols under analysis: {', '.join(context['symbols'])}\n")

        if "fear_greed_index" in context:
            parts.append(f"\nFear & Greed Index: {context['fear_greed_index']}\n")

        if "news_summary" in context:
            parts.append(f"\nRecent news and macro events:\n{context['news_summary']}\n")

        if "social_sentiment" in context:
            parts.append(f"\nSocial/X sentiment data:\n{context['social_sentiment']}\n")

        if "macro_data" in context:
            parts.append(f"\nMacroeconomic indicators:\n")
            parts.append(json.dumps(context["macro_data"], indent=2, default=str))

        parts.append(
            "\nProvide your sentiment analysis. What is the market mood? "
            "Are there any sentiment shifts or contrarian signals?"
        )

        return "\n".join(parts)
