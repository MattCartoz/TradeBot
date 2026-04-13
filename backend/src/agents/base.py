"""Base agent class — every agent on the trading desk inherits from this."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel

from src.llm.base import BaseLLMProvider, LLMMessage

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseAgent(ABC):
    """Abstract base for all trading desk agents.

    Each agent:
    - Has its own system prompt defining its role and constraints
    - Receives only the data it's authorized to see (isolation by design)
    - Returns structured JSON (Pydantic models)
    - Logs every invocation for audit trail
    """

    name: str
    role: str
    system_prompt: str

    def __init__(self, llm: BaseLLMProvider):
        self.llm = llm
        self._invocation_count = 0

    async def invoke(self, context: dict[str, Any], output_type: type[T]) -> T:
        """Run the agent: build prompt, call LLM, parse structured output.

        Args:
            context: The data this agent is allowed to see.
            output_type: Pydantic model class to parse the response into.

        Returns:
            Structured output conforming to the output_type schema.
        """
        self._invocation_count += 1
        started = datetime.utcnow()

        messages = self._build_messages(context, output_type)
        response = await self.llm.complete(messages, json_mode=True)

        try:
            raw = json.loads(response.content)
            result = output_type.model_validate(raw)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(
                "[%s] Failed to parse LLM response: %s\nRaw: %s",
                self.name, e, response.content[:500],
            )
            raise

        elapsed = (datetime.utcnow() - started).total_seconds()
        logger.info(
            "[%s] Invocation #%d completed in %.1fs (%d tokens)",
            self.name, self._invocation_count, elapsed, response.total_tokens,
        )

        return result

    def _build_messages(
        self, context: dict[str, Any], output_type: type[BaseModel]
    ) -> list[LLMMessage]:
        """Construct the message list for the LLM call."""
        schema_str = json.dumps(output_type.model_json_schema(), indent=2)

        system = (
            f"{self.system_prompt}\n\n"
            f"You MUST respond with valid JSON matching this exact schema:\n"
            f"```json\n{schema_str}\n```\n\n"
            f"Respond ONLY with the JSON object. No markdown, no explanation, no code fences."
        )

        user_content = self._format_context(context)

        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user_content),
        ]

    @abstractmethod
    def _format_context(self, context: dict[str, Any]) -> str:
        """Format the context data into a string for the LLM.

        Each agent subclass decides how to present its data.
        """
