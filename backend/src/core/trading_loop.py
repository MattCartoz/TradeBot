"""Main Trading Loop — orchestrates the full analysis cycle.

Each cycle:
1. Fetch market data (OHLCV, indicators, chart images)
2. Run analysts in parallel (Technical, Sentiment, Flow)
3. Strategist reads all briefs → StrategyDecision
4. Patience Engine gates the decision
5. Risk Manager approves/vetoes
6. Executor places the order (if approved)
7. Auditor reviews (after position closes)
8. Memory updates at every step
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from src.agents.auditor import Auditor
from src.agents.executor import Executor
from src.agents.flow_analyst import FlowAnalyst
from src.agents.risk_manager import RiskManager
from src.agents.sentiment_analyst import SentimentAnalyst
from src.agents.strategist import Strategist
from src.agents.technical_analyst import TechnicalAnalyst
from src.contracts import (
    AnalystBrief,
    ProposedAction,
    RiskDecision,
    StrategyDecision,
)
from src.core.config import Settings
from src.core.patience_engine import PatienceEngine
from src.data.chart_renderer import ChartRenderer
from src.data.indicators import compute_indicators
from src.data.market_data import MarketDataProvider
from src.exchange.base import BaseExchange
from src.llm.base import BaseLLMProvider
from src.memory.episodic import EpisodicMemory
from src.memory.semantic import SemanticMemory
from src.memory.working import WorkingMemory

logger = logging.getLogger(__name__)


class TradingLoop:
    """Orchestrates the full multi-agent trading cycle."""

    def __init__(
        self,
        settings: Settings,
        market_data: MarketDataProvider,
        exchange: BaseExchange,
        claude_llm: BaseLLMProvider,
        grok_llm: BaseLLMProvider | None,
        working_memory: WorkingMemory,
        episodic_memory: EpisodicMemory,
        semantic_memory: SemanticMemory,
        event_callback: Any | None = None,
    ):
        self.settings = settings
        self.market_data = market_data
        self.exchange = exchange
        self.working = working_memory
        self.episodic = episodic_memory
        self.semantic = semantic_memory
        self._event_callback = event_callback

        # Agents — each with its own LLM
        sentiment_llm = grok_llm or claude_llm
        self.technical_analyst = TechnicalAnalyst(claude_llm)
        self.sentiment_analyst = SentimentAnalyst(sentiment_llm)
        self.flow_analyst = FlowAnalyst(claude_llm)
        self.strategist = Strategist(claude_llm)
        self.risk_manager = RiskManager(claude_llm)
        self.executor = Executor(exchange)
        self.auditor = Auditor(claude_llm)

        self.patience = PatienceEngine(settings.patience)
        self.chart_renderer = ChartRenderer()
        self._running = False

    async def emit_event(self, event_type: str, data: dict) -> None:
        """Emit an event for the dashboard WebSocket."""
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "cycle": self.working.cycle_count,
            **data,
        }
        if self._event_callback:
            await self._event_callback(event)
        self.working.add_agent_log(event_type, data, self.working.cycle_count)

    async def run_cycle(self) -> dict:
        """Run one complete analysis cycle. Returns a summary dict."""
        self.working.cycle_count += 1
        cycle = self.working.cycle_count
        logger.info("=" * 60)
        logger.info("CYCLE #%d STARTING", cycle)
        logger.info("=" * 60)
        await self.emit_event("cycle_start", {"cycle": cycle})

        # 1. Update portfolio state
        portfolio_value = await self.exchange.get_portfolio_value()
        balances = await self.exchange.get_balance()
        self.working.update_portfolio(portfolio_value, balances.get("USD", 0))
        positions = await self.exchange.get_positions()

        # 2. Fetch market data and compute indicators
        symbols = self.settings.exchange.symbols
        timeframes = self.settings.exchange.timeframes

        all_indicators = []
        chart_images = []
        candle_summaries = {}

        for symbol in symbols:
            snapshot = await self.market_data.fetch_snapshot(symbol, timeframes)

            for tf, candles in snapshot.candles.items():
                if candles:
                    indicators = compute_indicators(candles, symbol, tf)
                    all_indicators.append(indicators)

                    try:
                        b64 = self.chart_renderer.render_base64(candles, symbol, tf)
                        chart_images.append((b64, f"{symbol} {tf}"))
                    except Exception as e:
                        logger.warning("Chart render failed for %s %s: %s", symbol, tf, e)

                    if tf == timeframes[0]:
                        last_5 = candles[-5:]
                        candle_summaries[symbol] = (
                            f"Last 5 candles ({tf}): "
                            + " → ".join(
                                f"O:{c.open:.2f} H:{c.high:.2f} L:{c.low:.2f} C:{c.close:.2f}"
                                for c in last_5
                            )
                        )

        # 3. Run analysts in PARALLEL (isolated — they can't see each other)
        await self.emit_event("analyst_phase", {"status": "starting"})

        tech_task = self.technical_analyst.analyze(
            chart_images=chart_images,
            indicators=all_indicators,
            candle_summaries=candle_summaries,
        )

        sentiment_context = {
            "symbols": symbols,
            "fear_greed_index": "N/A (connect Alternative.me API)",
            "news_summary": "Analyze current sentiment for: " + ", ".join(symbols),
            "social_sentiment": "Analyze X/Twitter sentiment for: " + ", ".join(symbols),
        }
        sentiment_task = self.sentiment_analyst.invoke(sentiment_context, AnalystBrief)

        flow_context = {
            "symbols": symbols,
            "volume_data": {s: candle_summaries.get(s, "N/A") for s in symbols},
        }
        flow_task = self.flow_analyst.invoke(flow_context, AnalystBrief)

        # Run all three in parallel
        tech_brief, sentiment_brief, flow_brief = await asyncio.gather(
            tech_task, sentiment_task, flow_task,
            return_exceptions=True,
        )

        briefs: list[AnalystBrief] = []
        for name, result in [("technical", tech_brief), ("sentiment", sentiment_brief), ("flow", flow_brief)]:
            if isinstance(result, Exception):
                logger.error("%s analyst failed: %s", name, result)
                await self.emit_event("agent_error", {"agent": name, "error": str(result)})
            else:
                briefs.append(result)
                await self.emit_event("analyst_brief", {
                    "agent": result.agent_name,
                    "conviction": result.conviction,
                    "regime": result.regime_signals.primary_signal.value,
                    "reasoning": result.reasoning[:200],
                })

        if not briefs:
            logger.error("All analysts failed — aborting cycle")
            return {"cycle": cycle, "action": "error", "reason": "All analysts failed"}

        # 4. Strategist reads all briefs
        playbook = self.semantic.get_playbook()
        strategy_context = {
            "analyst_briefs": [b.model_dump(mode="json") for b in briefs],
            "playbook": playbook,
            "current_positions": positions,
            "portfolio_value": portfolio_value,
        }
        decision = await self.strategist.invoke(strategy_context, StrategyDecision)
        await self.emit_event("strategy_decision", {
            "regime": decision.market_regime.value,
            "action": decision.proposed_action.value,
            "symbol": decision.symbol,
            "conviction": decision.conviction_score,
            "reasoning": decision.reasoning[:200],
        })

        # 5. Patience Engine check
        allowed, reason = self.patience.should_proceed(decision)
        if not allowed:
            logger.info("Patience Engine: %s", reason)
            await self.emit_event("patience_block", {"reason": reason})
            await self._record_cycle(cycle, briefs, decision, None, "hold", reason)
            self.working.save_to_disk()
            return {"cycle": cycle, "action": "hold", "reason": reason}

        # 6. Risk Manager
        from src.core.config import RiskConfig
        risk_context = {
            "strategy_decision": decision.model_dump(mode="json"),
            "risk_limits": self.settings.risk.model_dump(),
            "current_positions": positions,
            "portfolio_value": portfolio_value,
            "current_drawdown_pct": self.working.current_drawdown_pct,
            "trades_today": self.patience.state.trades_today,
        }

        from src.contracts import RiskAssessment
        risk_result = await self.risk_manager.invoke(risk_context, RiskAssessment)
        await self.emit_event("risk_assessment", {
            "decision": risk_result.decision.value,
            "reasoning": risk_result.reasoning[:200],
            "veto_reasons": risk_result.veto_reasons,
        })

        if risk_result.decision == RiskDecision.VETOED:
            logger.info("Risk Manager VETOED: %s", risk_result.veto_reasons)
            await self._record_cycle(
                cycle, briefs, decision, risk_result.model_dump(mode="json"), "vetoed",
                "; ".join(risk_result.veto_reasons),
            )
            self.working.save_to_disk()
            return {"cycle": cycle, "action": "vetoed", "reasons": risk_result.veto_reasons}

        # 7. Execute
        fill = await self.executor.execute(risk_result)
        if fill and fill.status.value == "filled":
            self.patience.record_trade()
            await self.emit_event("trade_executed", {
                "symbol": fill.symbol,
                "side": fill.side.value,
                "quantity": fill.filled_quantity,
                "price": fill.average_fill_price,
            })

            # Record in episodic memory
            trade_id = await self.episodic.record_trade_open(
                symbol=fill.symbol,
                side=fill.side.value,
                entry_price=fill.average_fill_price,
                quantity=fill.filled_quantity,
                analyst_briefs=[b.model_dump(mode="json") for b in briefs],
                strategy_decision=decision.model_dump(mode="json"),
                risk_assessment=risk_result.model_dump(mode="json"),
            )

            # Update working memory
            from src.memory.working import Position
            self.working.open_position(Position(
                symbol=fill.symbol,
                side=fill.side.value,
                quantity=fill.filled_quantity,
                entry_price=fill.average_fill_price,
                opened_at=datetime.utcnow().isoformat(),
                stop_loss=decision.stop_loss,
                take_profit=decision.target_price,
                trade_id=trade_id,
                analyst_briefs=[b.model_dump(mode="json") for b in briefs],
                strategy_decision=decision.model_dump(mode="json"),
                risk_assessment=risk_result.model_dump(mode="json"),
            ))

        await self._record_cycle(
            cycle, briefs, decision, risk_result.model_dump(mode="json"),
            "trade", decision.reasoning,
        )
        self.working.save_to_disk()

        logger.info("CYCLE #%d COMPLETE — trade executed", cycle)
        return {"cycle": cycle, "action": "trade", "fill": fill.model_dump(mode="json") if fill else None}

    async def _record_cycle(
        self, cycle: int, briefs: list[AnalystBrief],
        decision: StrategyDecision | None, risk: dict | None,
        action: str, reasoning: str,
    ) -> None:
        await self.episodic.record_cycle(
            cycle_number=cycle,
            analyst_briefs=[b.model_dump(mode="json") for b in briefs],
            strategy_decision=decision.model_dump(mode="json") if decision else None,
            risk_assessment=risk,
            action_taken=action,
            reasoning=reasoning,
        )

    async def run(self) -> None:
        """Run the trading loop continuously."""
        self._running = True
        interval = self.settings.cycle.interval_minutes * 60
        logger.info("Trading loop started — cycle every %d minutes", self.settings.cycle.interval_minutes)

        while self._running:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error("Cycle failed: %s", e, exc_info=True)
                await self.emit_event("cycle_error", {"error": str(e)})

            await asyncio.sleep(interval)

    def stop(self) -> None:
        self._running = False
        logger.info("Trading loop stop requested")
