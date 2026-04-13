"""xAI Grok LLM provider — social/sentiment analysis with native X integration."""

from __future__ import annotations

import logging
import os

from openai import AsyncOpenAI

from .base import BaseLLMProvider, ImageContent, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class GrokProvider(BaseLLMProvider):
    """Grok API provider — used for Sentiment Analyst (native X/Twitter access)."""

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
