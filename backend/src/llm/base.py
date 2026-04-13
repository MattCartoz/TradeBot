"""Base LLM provider interface — all providers implement this contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str  # "system", "user", "assistant"
    content: str | list[dict]  # str for text, list for multimodal (text + images)


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ImageContent:
    """Image for multimodal vision analysis."""
    base64_data: str
    media_type: str = "image/png"

    def to_message_block(self, provider: str) -> dict:
        """Format image block for the specific LLM provider."""
        if provider in ("claude", "anthropic"):
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": self.media_type,
                    "data": self.base64_data,
                },
            }
        elif provider in ("openai", "grok"):
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{self.media_type};base64,{self.base64_data}",
                },
            }
        raise ValueError(f"Unknown provider: {provider}")


class BaseLLMProvider(ABC):
    """Interface that all LLM providers must implement."""

    provider_name: str

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 4096,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Send messages to the LLM and get a response."""

    @abstractmethod
    async def complete_with_images(
        self,
        system_prompt: str,
        text_content: str,
        images: list[ImageContent],
        max_tokens: int = 4096,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Send text + images to a vision-capable LLM."""

    async def close(self) -> None:
        """Clean up resources."""
