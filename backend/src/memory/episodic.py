"""Episodic Memory — Tier 2: PostgreSQL trade history with full reasoning.

Every trade with entry reasoning, analyst briefs, outcome, and post-mortem.
Every analysis cycle is logged, even when no trade occurs.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class TradeRecord(Base):
    __tablename__ = "trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    entry_price = Column(Float)
    exit_price = Column(Float)
    quantity = Column(Float)
    pnl = Column(Float)
    pnl_pct = Column(Float)
    entry_reasoning = Column(JSONB)
    exit_reasoning = Column(JSONB)
    analyst_briefs = Column(JSONB)
    strategy_decision = Column(JSONB)
    risk_assessment = Column(JSONB)
    post_mortem = Column(JSONB)
    opened_at = Column(DateTime, default=func.now())
    closed_at = Column(DateTime)
    status = Column(String(20), default="open", index=True)


class AnalysisCycleRecord(Base):
    __tablename__ = "analysis_cycles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cycle_number = Column(Float, index=True)
    timestamp = Column(DateTime, default=func.now())
    analyst_briefs = Column(JSONB)
    strategy_decision = Column(JSONB)
    risk_assessment = Column(JSONB)
    action_taken = Column(String(20))
    reasoning = Column(Text)
    tokens_used = Column(Float, default=0)


class EpisodicMemory:
    """PostgreSQL-backed trade and cycle history."""

    def __init__(self, database_url: str):
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def initialize(self) -> None:
        """Create tables if they don't exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Episodic memory tables initialized")

    async def record_trade_open(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        analyst_briefs: list[dict],
        strategy_decision: dict,
        risk_assessment: dict,
    ) -> str:
        """Record a new trade opening. Returns trade_id."""
        trade_id = uuid.uuid4()
        async with self._session_factory() as session:
            trade = TradeRecord(
                id=trade_id,
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                quantity=quantity,
                analyst_briefs=analyst_briefs,
                strategy_decision=strategy_decision,
                risk_assessment=risk_assessment,
                entry_reasoning=strategy_decision,
                status="open",
            )
            session.add(trade)
            await session.commit()
        return str(trade_id)

    async def record_trade_close(
        self,
        trade_id: str,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        post_mortem: dict | None = None,
    ) -> None:
        """Record a trade closing with outcome."""
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TradeRecord).where(TradeRecord.id == uuid.UUID(trade_id))
            )
            trade = result.scalar_one_or_none()
            if trade:
                trade.exit_price = exit_price
                trade.pnl = pnl
                trade.pnl_pct = pnl_pct
                trade.post_mortem = post_mortem
                trade.closed_at = datetime.utcnow()
                trade.status = "closed"
                await session.commit()

    async def record_cycle(
        self,
        cycle_number: int,
        analyst_briefs: list[dict],
        strategy_decision: dict | None,
        risk_assessment: dict | None,
        action_taken: str,
        reasoning: str,
        tokens_used: int = 0,
    ) -> None:
        """Record an analysis cycle (whether or not a trade occurred)."""
        async with self._session_factory() as session:
            cycle = AnalysisCycleRecord(
                cycle_number=cycle_number,
                analyst_briefs=analyst_briefs,
                strategy_decision=strategy_decision,
                risk_assessment=risk_assessment,
                action_taken=action_taken,
                reasoning=reasoning,
                tokens_used=tokens_used,
            )
            session.add(cycle)
            await session.commit()

    async def get_recent_trades(self, limit: int = 20) -> list[dict]:
        """Get recent trades for dashboard."""
        async with self._session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(TradeRecord)
                .order_by(TradeRecord.opened_at.desc())
                .limit(limit)
            )
            trades = result.scalars().all()
            return [
                {
                    "id": str(t.id),
                    "symbol": t.symbol,
                    "side": t.side,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "quantity": t.quantity,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "status": t.status,
                    "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                    "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                    "post_mortem": t.post_mortem,
                }
                for t in trades
            ]

    async def close(self) -> None:
        await self._engine.dispose()
