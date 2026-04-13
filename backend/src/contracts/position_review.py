"""Structured output contract for the Position Manager agent."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PositionAction(str, Enum):
    HOLD = "hold"
    ADJUST_STOP = "adjust_stop"  # Move stop-loss
    TAKE_PARTIAL = "take_partial"  # Sell part of position
    CLOSE = "close"  # Close entire position


class PositionReview(BaseModel):
    """Per-position decision from the Position Manager."""

    symbol: str
    action: PositionAction
    new_stop_loss: float | None = Field(
        default=None,
        description="New stop-loss price. Required when action is adjust_stop.",
    )
    partial_close_pct: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Fraction of position to close. Required when action is take_partial. "
            "E.g. 0.5 = sell 50%."
        ),
    )
    reasoning: str = Field(
        description="Full reasoning for this decision — audit trail."
    )
    thesis_still_valid: bool = Field(
        description="Whether the original entry thesis still holds."
    )
    urgency: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How urgently this action should be executed. "
            "0.0 = no rush, 1.0 = immediate."
        ),
    )


class PositionManagerOutput(BaseModel):
    """Output contract for the Position Manager — reviews all open positions each cycle."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reviews: list[PositionReview] = Field(
        description="One review per open position."
    )
