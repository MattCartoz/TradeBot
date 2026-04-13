"""Structured output contract for the Strategist agent."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    DEAD = "dead"


class ProposedAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"


class StrategyDecision(BaseModel):
    """Output contract for the Strategist — the central decision-maker."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    market_regime: MarketRegime
    regime_confidence: float = Field(ge=0.0, le=1.0)
    selected_strategy: str = Field(description="Strategy name from the playbook")
    proposed_action: ProposedAction
    symbol: str
    entry_price: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    position_size_pct: float = Field(
        ge=0.0, le=100.0, description="Suggested position size as % of portfolio"
    )
    conviction_score: float = Field(
        ge=0.0, le=1.0, description="Must exceed patience threshold to proceed"
    )
    reasoning: str
    analyst_agreement: float = Field(
        ge=0.0, le=1.0, description="How aligned the analyst briefs are"
    )
    dissenting_views: list[str] = Field(
        default_factory=list, description="Notable disagreements between analysts"
    )
