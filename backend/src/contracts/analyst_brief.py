"""Structured output contract for all Analyst agents."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class RegimeSignal(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    DEAD = "dead"


class SignalDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class Opportunity(BaseModel):
    symbol: str
    direction: SignalDirection
    setup_type: str = Field(description="E.g. 'ascending_triangle', 'breakout', 'mean_reversion'")
    entry_zone: float | None = None
    target: float | None = None
    stop_loss: float | None = None
    timeframe: str = Field(description="E.g. '4h', '1d'")
    notes: str = ""


class Risk(BaseModel):
    symbol: str
    risk_type: str = Field(description="E.g. 'resistance_overhead', 'divergence', 'news_event'")
    severity: float = Field(ge=0.0, le=1.0, description="0 = minor, 1 = critical")
    description: str


class RegimeSignals(BaseModel):
    primary_signal: RegimeSignal
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str] = Field(default_factory=list)


class AnalystBrief(BaseModel):
    """Output contract for Technical, Sentiment, and Flow analysts."""

    agent_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    symbols_analyzed: list[str]
    timeframes_analyzed: list[str]
    regime_signals: RegimeSignals
    opportunities: list[Opportunity] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    conviction: float = Field(ge=0.0, le=1.0, description="Overall conviction in the analysis")
    reasoning: str = Field(description="Free-text reasoning for audit trail")
    data_quality: float = Field(
        ge=0.0, le=1.0, default=1.0, description="Confidence in input data quality"
    )
