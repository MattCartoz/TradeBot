"""Anthropic Claude LLM provider — deep reasoning, strategy, vision analysis."""

from __future__ import annotations

import logging
import os

import anthropic

from .base import BaseLLMProvider, ImageContent, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseLLMProvider):
    """Claude API provider — used for Strategist, Risk Manager, Auditor, and vision analysis."""

    provider_name = "claude"

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        self.model = model
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )

    async def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 4096,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> LLMResponse:
        system_prompt = None
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content if isinstance(msg.content, str) else str(msg.content)
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": api_messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self._client.messages.create(**kwargs)

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        logger.debug(
            "Claude response: %d input, %d output tokens",
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        return LLMResponse(
            content=content,
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason or "",
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
        """Send chart images + text to Claude's vision API."""
        content_blocks: list[dict] = []

        for img in images:
            content_blocks.append(img.to_message_block("claude"))

        content_blocks.append({"type": "text", "text": text_content})

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=content_blocks),
        ]
        return await self.complete(messages, max_tokens, temperature, json_mode)

    async def close(self) -> None:
        await self._client.close()
