"""Inter-agent JSON contracts — Pydantic models defining how agents communicate."""

from .analyst_brief import (
    AnalystBrief,
    Opportunity,
    RegimeSignal,
    RegimeSignals,
    Risk,
    SignalDirection,
)
from .debate import DebateArgument, DebateSummary
from .execution_order import ExecutionOrder, FillReport, OrderSide, OrderStatus, OrderType
from .position_review import PositionAction, PositionManagerOutput, PositionReview
from .post_mortem import PlaybookUpdate, TradeOutcome, TradePostMortem
from .risk_assessment import RiskAssessment, RiskDecision
from .strategy_decision import MarketRegime, ProposedAction, StrategyDecision

__all__ = [
    "AnalystBrief",
    "DebateArgument",
    "DebateSummary",
    "ExecutionOrder",
    "FillReport",
    "MarketRegime",
    "Opportunity",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PlaybookUpdate",
    "PositionAction",
    "PositionManagerOutput",
    "PositionReview",
    "ProposedAction",
    "RegimeSignal",
    "RegimeSignals",
    "Risk",
    "RiskAssessment",
    "RiskDecision",
    "SignalDirection",
    "StrategyDecision",
    "TradeOutcome",
    "TradePostMortem",
]
