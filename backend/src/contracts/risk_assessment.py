"""Structured output contract for the Risk Manager agent."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from .execution_order import ExecutionOrder


class RiskDecision(str, Enum):
    APPROVED = "approved"
    VETOED = "vetoed"
    MODIFIED = "modified"


class RiskAssessment(BaseModel):
    """Output contract for the Risk Manager — has hard veto power."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    decision: RiskDecision
    veto_reasons: list[str] = Field(
        default_factory=list, description="Why rejected (if vetoed)"
    )
    modifications: list[str] = Field(
        default_factory=list, description="What was changed (if modified)"
    )
    approved_order: ExecutionOrder | None = None
    portfolio_risk_after: float = Field(
        ge=0.0, le=100.0, description="Projected total portfolio risk %"
    )
    max_drawdown_remaining: float = Field(
        ge=0.0, description="How much drawdown budget remains %"
    )
    correlation_check: bool = Field(
        description="Whether the trade passes correlation limits"
    )
    reasoning: str = Field(description="Full reasoning for audit trail")
