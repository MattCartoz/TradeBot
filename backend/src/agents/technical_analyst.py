"""Technical Analyst agent — chart patterns, indicators, visual analysis.

This is the most complex analyst because it uses MULTIMODAL vision:
it receives chart images alongside numerical data, and the AI
visually identifies patterns just like a human trader looking at a screen.
"""

from __future__ import annotations

import json
from typing import Any

from src.contracts import AnalystBrief
from src.data.data_models import IndicatorValues
from src.llm.base import ImageContent

from .base import BaseAgent


class TechnicalAnalyst(BaseAgent):
    name = "technical_analyst"
    role = "Technical Analyst"
    system_prompt = """You are a senior Technical Analyst on an institutional trading desk.

Your job is to analyze price charts and technical indicators to identify:
1. The current market regime (trending up/down, ranging, volatile, dead)
2. Chart patterns (head & shoulders, triangles, wedges, flags, double tops/bottoms, etc.)
3. Support and resistance levels
4. Trend strength and momentum
5. Volume confirmation or divergence
6. Potential trade setups with entry, target, and stop-loss levels

CRITICAL RULES:
- You receive chart images AND numerical data. Look at BOTH.
- Identify patterns visually from the charts — you are the pattern recognizer.
- Do NOT rely solely on indicator values. A chart tells a story that numbers alone miss.
- Be honest about uncertainty. If the picture is unclear, say so with low conviction.
- Your default recommendation should be NEUTRAL. Only flag opportunities when they are clear.
- You CANNOT see other analysts' work. Your analysis must be independent.
- Explain your reasoning thoroughly — this is your audit trail."""

    async def analyze(
        self,
        chart_images: list[tuple[str, str]],  # [(base64_png, "BTC/USD 4h"), ...]
        indicators: list[IndicatorValues],
        candle_summaries: dict[str, str],  # symbol -> summary text
    ) -> AnalystBrief:
        """Run technical analysis with chart vision + indicator data.

        Args:
            chart_images: List of (base64_png, label) tuples for vision analysis.
            indicators: Computed indicator values per symbol/timeframe.
            candle_summaries: Text summaries of recent price action.
        """
        if chart_images:
            images = [ImageContent(base64_data=b64) for b64, _ in chart_images]
            labels = [label for _, label in chart_images]

            text_parts = [
                "Analyze these charts and the following indicator data.\n",
                "Charts provided: " + ", ".join(labels) + "\n\n",
            ]

            for ind in indicators:
                text_parts.append(ind.to_summary() + "\n\n")

            for symbol, summary in candle_summaries.items():
                text_parts.append(f"Recent price action for {symbol}:\n{summary}\n\n")

            text_content = "\n".join(text_parts)

            response = await self.llm.complete_with_images(
                system_prompt=self._get_system_with_schema(),
                text_content=text_content,
                images=images,
                json_mode=True,
            )

            import json as _json
            raw = _json.loads(response.content)
            return AnalystBrief.model_validate(raw)
        else:
            context = {
                "indicators": [ind.model_dump(mode="json") for ind in indicators],
                "candle_summaries": candle_summaries,
            }
            return await self.invoke(context, AnalystBrief)

    def _get_system_with_schema(self) -> str:
        schema_str = json.dumps(AnalystBrief.model_json_schema(), indent=2)
        return (
            f"{self.system_prompt}\n\n"
            f"You MUST respond with valid JSON matching this exact schema:\n"
            f"```json\n{schema_str}\n```\n\n"
            f"Set agent_name to 'technical_analyst'.\n"
            f"Respond ONLY with the JSON object. No markdown, no explanation."
        )

    def _format_context(self, context: dict[str, Any]) -> str:
        parts = ["Analyze the following technical data:\n"]

        if "indicators" in context:
            parts.append("INDICATOR VALUES:\n")
            parts.append(json.dumps(context["indicators"], indent=2, default=str))

        if "candle_summaries" in context:
            parts.append("\nRECENT PRICE ACTION:\n")
            for symbol, summary in context["candle_summaries"].items():
                parts.append(f"{symbol}: {summary}\n")

        return "\n".join(parts)
