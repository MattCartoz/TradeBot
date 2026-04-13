"""Structured output contracts for the Bull/Bear Debate agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DebateArgument(BaseModel):
    """A single side of the bull/bear debate."""

    position: Literal["bull", "bear"]
    thesis: str = Field(description="Core argument — one-paragraph summary of the case")
    key_points: list[str] = Field(
        min_length=3,
        max_length=5,
        description="3-5 supporting points with evidence",
    )
    risk_factors: list[str] = Field(
        description="Acknowledged weaknesses in this side's own argument"
    )
    conviction: float = Field(
        ge=0.0, le=1.0, description="Strength of conviction in this argument"
    )
    recommended_action: str = Field(
        description="Recommended action: 'buy', 'sell', or 'hold'"
    )


class DebateSummary(BaseModel):
    """Combined output of the bull/bear debate — consumed by the Strategist."""

    bull_argument: DebateArgument
    bear_argument: DebateArgument
    consensus_direction: str = Field(
        description="Which side has the stronger case: 'bull', 'bear', or 'neutral'"
    )
    agreement_level: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = total disagreement, 1.0 = total agreement",
    )
    key_disagreements: list[str] = Field(
        description="Specific points where bull and bear fundamentally disagree"
    )
