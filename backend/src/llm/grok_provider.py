"""xAI Grok LLM provider — social/sentiment analysis with native X search.

Grok's API supports tool use. We define an X search tool so Grok can
pull real-time X/Twitter posts about the symbols we're analyzing.
The model decides what to search for and synthesizes the sentiment.
"""

from __future__ import annotations

import json
import logging
import os

from openai import AsyncOpenAI

from .base import BaseLLMProvider, ImageContent, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)

# X search tool definition — Grok calls this to search X natively
X_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_x",
        "description": (
            "Search X/Twitter for recent posts about a topic. "
            "Returns real-time social sentiment, trending discussions, "
            "and notable posts from traders, analysts, and influencers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for X/Twitter posts",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return (5-20)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
}


class GrokProvider(BaseLLMProvider):
    """Grok API provider — used for Sentiment Analyst with native X/Twitter access.

    Uses xAI's OpenAI-compatible API. When search_mode is enabled,
    Grok will use its built-in knowledge of X/Twitter to analyze
    real-time social sentiment for the requested symbols.
    """

    provider_name = "grok"

    def __init__(self, model: str = "grok-3", api_key: str | None = None):
        self.model = model
        self._client = AsyncOpenAI(
            api_key=api_key or os.environ.get("XAI_API_KEY"),
            base_url="https://api.x.ai/v1",
        )

    async def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 4096,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> LLMResponse:
        api_messages = []
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})

        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": api_messages,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content or ""
        usage = response.usage

        logger.debug(
            "Grok response: %d input, %d output tokens",
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )

        return LLMResponse(
            content=content,
            model=self.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            stop_reason=response.choices[0].finish_reason or "",
        )

    async def search_x_sentiment(
        self,
        symbols: list[str],
        additional_context: str = "",
    ) -> str:
        """Ask Grok to analyze X/Twitter sentiment for given symbols.

        Grok has native access to X data through its training and real-time
        capabilities. We instruct it to search and analyze sentiment
        specifically for our trading symbols.

        Returns: A structured text summary of X sentiment.
        """
        symbol_list = ", ".join(symbols)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a social media sentiment analyst specializing in crypto and "
                    "financial markets. You have access to real-time X/Twitter data. "
                    "Analyze the current sentiment, trending narratives, and notable posts "
                    "for the requested symbols. Be specific about what you find — "
                    "quote notable posts, identify sentiment shifts, and flag any "
                    "unusual activity (whale alerts, influencer calls, FUD campaigns)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Analyze the current X/Twitter sentiment for: {symbol_list}\n\n"
                    f"Search for:\n"
                    f"1. What are traders saying about {symbol_list} right now?\n"
                    f"2. Is sentiment shifting bullish or bearish? What's the ratio?\n"
                    f"3. Any notable influencer posts or whale alerts?\n"
                    f"4. Any trending hashtags or narratives forming?\n"
                    f"5. Is retail sentiment at an extreme (could be contrarian signal)?\n"
                    f"\n{additional_context}\n\n"
                    f"Be honest if sentiment is unclear or mixed. Don't make up data."
                ),
            },
        ]

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2048,
                temperature=0.3,
            )
            return response.choices[0].message.content or "X sentiment analysis unavailable"
        except Exception as e:
            logger.error("Grok X sentiment search failed: %s", e)
            return f"X sentiment search failed: {e}"

    async def complete_with_images(
        self,
        system_prompt: str,
        text_content: str,
        images: list[ImageContent],
        max_tokens: int = 4096,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Send text + images to Grok's vision API."""
        content_blocks: list[dict] = []
        for img in images:
            content_blocks.append(img.to_message_block("grok"))
        content_blocks.append({"type": "text", "text": text_content})

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=content_blocks),
        ]
        return await self.complete(messages, max_tokens, temperature, json_mode)

    async def close(self) -> None:
        await self._client.close()
