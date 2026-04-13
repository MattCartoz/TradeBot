"""Structured output contract for the Auditor agent."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TradeOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class PlaybookUpdate(BaseModel):
    """A specific update the Auditor recommends for the strategy playbook."""

    update_type: str = Field(description="E.g. 'add_rule', 'modify_strategy', 'adjust_threshold'")
    target: str = Field(description="Which strategy or rule to update")
    change: str = Field(description="What the change should be")
    reasoning: str


class TradePostMortem(BaseModel):
    """Output contract for the Auditor — reviews every closed trade."""

    trade_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    symbol: str
    entry_reasoning: str
    exit_reasoning: str
    outcome: TradeOutcome
    pnl_absolute: float
    pnl_percentage: float
    hold_duration_minutes: float
    what_went_right: list[str] = Field(default_factory=list)
    what_went_wrong: list[str] = Field(default_factory=list)
    pattern_accuracy: float = Field(
        ge=0.0, le=1.0, description="Was the technical/visual pattern read correctly?"
    )
    regime_accuracy: bool = Field(description="Was the market regime classification correct?")
    playbook_updates: list[PlaybookUpdate] = Field(
        default_factory=list, description="Suggested changes to the playbook"
    )
    lessons: list[str] = Field(default_factory=list)
