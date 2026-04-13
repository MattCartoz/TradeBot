"""Main Trading Loop — orchestrates the full analysis cycle.

Each cycle:
1. Fetch ALL data in parallel (OHLCV, order book, external APIs)
2. Compute indicators + render charts
3. Check open positions for stop-loss / take-profit exits
4. Run analysts in parallel (Technical, Sentiment, Flow) with REAL data
5. Strategist reads all briefs → StrategyDecision
6. Patience Engine gates the decision
7. Risk Manager approves/vetoes
8. Executor places the order (if approved)
9. Auditor reviews closed positions → playbook updates
10. Memory updates at every step
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from src.agents.auditor import Auditor
from src.agents.debate import BullResearcher, BearResearcher, run_debate
from src.agents.executor import Executor
from src.agents.flow_analyst import FlowAnalyst
from src.agents.position_manager import PositionManager
from src.agents.risk_manager import RiskManager
from src.agents.sentiment_analyst import SentimentAnalyst
from src.agents.strategist import Strategist
from src.agents.technical_analyst import TechnicalAnalyst
from src.contracts import (
    AnalystBrief,
    PositionAction,
    PositionManagerOutput,
    RiskAssessment,
    RiskDecision,
    StrategyDecision,
    TradePostMortem,
)
from src.contracts.debate import DebateSummary
from src.core.config import Settings
from src.core.patience_engine import PatienceEngine
from src.data.chart_renderer import ChartRenderer
from src.data.external_sources import fetch_all_external_data, close_client as close_http
from src.data.indicators import compute_indicators
from src.data.market_data import MarketDataProvider
from src.exchange.base import BaseExchange
from src.llm.base import BaseLLMProvider
from src.llm.grok_provider import GrokProvider
from src.memory.episodic import EpisodicMemory
from src.memory.semantic import SemanticMemory
from src.memory.working import Position, WorkingMemory

logger = logging.getLogger(__name__)


class TradingLoop:
    """Orchestrates the full multi-agent trading cycle."""

    def __init__(
        self,
        settings: Settings,
        market_data: MarketDataProvider,
        exchange: BaseExchange,
        claude_llm: BaseLLMProvider,
        grok_llm: GrokProvider | None,
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

        # Store raw providers for direct access
        self._grok = grok_llm
        self._claude = claude_llm

        # Agents — each with its designated LLM
        sentiment_llm = grok_llm or claude_llm
        self.technical_analyst = TechnicalAnalyst(claude_llm)
        self.sentiment_analyst = SentimentAnalyst(sentiment_llm)
        self.flow_analyst = FlowAnalyst(claude_llm)
        self.strategist = Strategist(claude_llm)
        self.risk_manager = RiskManager(claude_llm)
        self.executor = Executor(exchange)
        self.auditor = Auditor(claude_llm)
        self.position_manager = PositionManager(claude_llm)
        self.bull_researcher = BullResearcher(claude_llm)
        self.bear_researcher = BearResearcher(claude_llm)

        self.patience = PatienceEngine(settings.patience)
        self.chart_renderer = ChartRenderer()
        self._running = False
        self._notifier = None  # Set by app.py after construction

    # ── Event Broadcasting ──────────────────────────────────

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

    # ── Main Cycle ──────────────────────────────────────────

    async def run_cycle(self) -> dict:
        """Run one complete analysis cycle."""
        self.working.cycle_count += 1
        cycle = self.working.cycle_count
        logger.info("=" * 60)
        logger.info("CYCLE #%d STARTING", cycle)
        logger.info("=" * 60)
        await self.emit_event("cycle_start", {"cycle": cycle})

        # ── Step 1: Portfolio state ──────────────────────────
        portfolio_value = await self.exchange.get_portfolio_value()
        balances = await self.exchange.get_balance()
        self.working.update_portfolio(portfolio_value, balances.get("USD", 0))
        positions = await self.exchange.get_positions()

        # ── Step 2: Check open positions for exits ───────────
        await self._check_position_exits(positions)

        # ── Step 3: Fetch ALL data in parallel ───────────────
        symbols = self.settings.exchange.symbols
        timeframes = self.settings.exchange.timeframes

        # Kick off external data fetch in parallel with market data
        external_data_task = fetch_all_external_data()

        # Fetch X/Twitter sentiment via Grok (parallel)
        x_sentiment_task = None
        if self._grok and hasattr(self._grok, "search_x_sentiment"):
            x_sentiment_task = self._grok.search_x_sentiment(symbols)

        # Fetch market snapshots (OHLCV + order book + ticker)
        snapshots = {}
        for symbol in symbols:
            snapshots[symbol] = await self.market_data.fetch_snapshot(
                symbol, timeframes
            )

        # Await the parallel external fetches
        external_data = await external_data_task
        x_sentiment = ""
        if x_sentiment_task:
            try:
                x_sentiment = await x_sentiment_task
            except Exception as e:
                logger.warning("Grok X sentiment fetch failed: %s", e)
                x_sentiment = f"X sentiment unavailable: {e}"

        logger.info(
            "Data collected: %d symbols, external=%s, x_sentiment=%d chars",
            len(snapshots),
            "ok" if external_data.get("fear_greed") else "partial",
            len(x_sentiment),
        )

        # ── Step 4: Process market data ──────────────────────
        all_indicators = []
        chart_images = []
        ohlcv_data = {}  # symbol -> {timeframe -> candles as dicts}
        order_book_summaries = {}
        candle_summaries = {}

        for symbol, snapshot in snapshots.items():
            ohlcv_data[symbol] = {}

            # Order book
            if snapshot.order_book:
                order_book_summaries[symbol] = snapshot.order_book.to_summary()

            for tf, candles in snapshot.candles.items():
                if not candles:
                    continue

                # Store raw OHLCV as dicts for the analysts
                ohlcv_data[symbol][tf] = [c.model_dump(mode="json") for c in candles[-20:]]

                # Compute indicators
                indicators = compute_indicators(candles, symbol, tf)
                all_indicators.append(indicators)

                # Render chart images for AI vision
                try:
                    b64 = self.chart_renderer.render_base64(candles, symbol, tf)
                    chart_images.append((b64, f"{symbol} {tf}"))
                except Exception as e:
                    logger.warning("Chart render failed for %s %s: %s", symbol, tf, e)

                # Build candle summary (last 10 candles, primary timeframe)
                if tf == timeframes[0]:
                    recent = candles[-10:]
                    lines = [f"Recent price action for {symbol} ({tf}), last {len(recent)} candles:"]
                    for c in recent:
                        direction = "UP" if c.close > c.open else "DOWN"
                        body_pct = abs(c.close - c.open) / c.open * 100
                        lines.append(
                            f"  {c.timestamp.strftime('%m/%d %H:%M')} "
                            f"O:{c.open:.2f} H:{c.high:.2f} L:{c.low:.2f} C:{c.close:.2f} "
                            f"V:{c.volume:.0f} ({direction} {body_pct:.1f}%)"
                        )
                    candle_summaries[symbol] = "\n".join(lines)

        await self.emit_event("data_collected", {
            "symbols": symbols,
            "chart_images": len(chart_images),
            "indicators": len(all_indicators),
            "fear_greed": external_data.get("fear_greed", {}).get("value", "N/A"),
        })

        # ── Step 5: Run Analysts in PARALLEL (isolated) ──────
        await self.emit_event("analyst_phase", {"status": "starting"})

        # TECHNICAL ANALYST: Charts + indicators + OHLCV + order book
        tech_task = self.technical_analyst.analyze(
            chart_images=chart_images,
            indicators=all_indicators,
            candle_summaries=candle_summaries,
            ohlcv_json=ohlcv_data,
            order_book_summaries=order_book_summaries,
        )

        # SENTIMENT ANALYST: Real Fear & Greed + FRED macro + X sentiment
        fear_greed = external_data.get("fear_greed", {})
        macro_data = external_data.get("macro", {})
        sentiment_context = {
            "symbols": symbols,
            "fear_greed_index": (
                f"Value: {fear_greed.get('value', 'N/A')} "
                f"({fear_greed.get('label', 'N/A')}). "
                f"7-day history: {json.dumps(fear_greed.get('history_7d', []))}"
            ),
            "social_sentiment": x_sentiment or "X/Twitter sentiment data not available this cycle.",
            "macro_data": macro_data,
            "news_summary": (
                "Use the macro indicators and social sentiment above to assess "
                "the current news and macro environment. Focus on what's changed "
                "recently and what narratives are driving price action."
            ),
        }
        sentiment_task = self.sentiment_analyst.invoke(sentiment_context, AnalystBrief)

        # FLOW ANALYST: Order book depth + volume data + on-chain (DeFiLlama)
        defi_data = external_data.get("defi", {})
        volume_analysis = {}
        for symbol in symbols:
            parts = []
            for ind in all_indicators:
                if ind.symbol == symbol:
                    if ind.obv is not None:
                        parts.append(f"OBV ({ind.timeframe}): {ind.obv:,.0f}")
                    if ind.volume_sma_20 is not None:
                        parts.append(f"Volume SMA20 ({ind.timeframe}): {ind.volume_sma_20:,.0f}")
            volume_analysis[symbol] = "\n".join(parts) if parts else "Limited volume data"

        flow_context = {
            "symbols": symbols,
            "volume_data": volume_analysis,
            "order_book": {s: order_book_summaries.get(s, "Order book unavailable") for s in symbols},
            "on_chain": {
                "defi_tvl": defi_data.get("total_tvl_formatted", "N/A"),
                "top_protocols": defi_data.get("top_protocols", [])[:5],
                "chain_tvl": defi_data.get("chains", {}),
            },
        }
        flow_task = self.flow_analyst.invoke(flow_context, AnalystBrief)

        # Run all three analysts in parallel
        tech_brief, sentiment_brief, flow_brief = await asyncio.gather(
            tech_task, sentiment_task, flow_task,
            return_exceptions=True,
        )

        briefs: list[AnalystBrief] = []
        for name, result in [
            ("technical", tech_brief),
            ("sentiment", sentiment_brief),
            ("flow", flow_brief),
        ]:
            if isinstance(result, Exception):
                logger.error("%s analyst failed: %s", name, result)
                await self.emit_event("agent_error", {"agent": name, "error": str(result)})
            else:
                briefs.append(result)
                await self.emit_event("analyst_brief", {
                    "agent": result.agent_name,
                    "conviction": result.conviction,
                    "regime": result.regime_signals.primary_signal.value,
                    "reasoning": result.reasoning[:300],
                })

        if not briefs:
            logger.error("All analysts failed — aborting cycle")
            await self._record_cycle(cycle, [], None, None, "error", "All analysts failed")
            return {"cycle": cycle, "action": "error", "reason": "All analysts failed"}

        # ── Step 5b: Position Manager (AI-driven exit management) ──
        if self.working.positions:
            indicator_by_symbol = {}
            for ind in all_indicators:
                indicator_by_symbol.setdefault(ind.symbol, []).append(ind)

            pm_context = {
                "positions": [
                    {
                        "symbol": p.symbol,
                        "side": p.side,
                        "quantity": p.quantity,
                        "entry_price": p.entry_price,
                        "stop_loss": p.stop_loss,
                        "take_profit": p.take_profit,
                        "opened_at": p.opened_at,
                        "entry_reasoning": p.strategy_decision.get("reasoning", ""),
                    }
                    for p in self.working.positions.values()
                ],
                "current_prices": {
                    s: {"last": snap.ticker.last, "bid": snap.ticker.bid, "ask": snap.ticker.ask}
                    for s, snap in snapshots.items()
                    if snap.ticker
                },
                "indicators": {
                    s: [i.to_summary() for i in inds]
                    for s, inds in indicator_by_symbol.items()
                },
                "market_regime": briefs[0].regime_signals.primary_signal.value if briefs else "unknown",
                "portfolio_value": portfolio_value,
            }
            try:
                pm_output = await self.position_manager.review_positions(pm_context)
                for review in pm_output.reviews:
                    if review.action == PositionAction.CLOSE:
                        price = pm_context["current_prices"].get(review.symbol, {}).get("last", 0)
                        if price and review.symbol in self.working.positions:
                            await self.emit_event("position_manager_close", {
                                "symbol": review.symbol,
                                "reasoning": review.reasoning[:200],
                            })
                            pos = self.working.positions[review.symbol]
                            await self._close_and_audit_position(pos, price, "position_manager")
                    elif review.action == PositionAction.ADJUST_STOP and review.new_stop_loss:
                        if review.symbol in self.working.positions:
                            self.working.positions[review.symbol].stop_loss = review.new_stop_loss
                            await self.emit_event("stop_adjusted", {
                                "symbol": review.symbol,
                                "new_stop": review.new_stop_loss,
                                "reasoning": review.reasoning[:200],
                            })
                    elif review.action == PositionAction.TAKE_PARTIAL and review.partial_close_pct:
                        if review.symbol in self.working.positions:
                            pos = self.working.positions[review.symbol]
                            partial_qty = pos.quantity * review.partial_close_pct
                            if partial_qty > 0:
                                from src.contracts import ExecutionOrder, OrderSide, OrderType
                                close_side = OrderSide.SELL if pos.side == "buy" else OrderSide.BUY
                                partial_order = ExecutionOrder(
                                    symbol=pos.symbol,
                                    side=close_side,
                                    order_type=OrderType.MARKET,
                                    quantity=partial_qty,
                                )
                                try:
                                    fill = await self.exchange.submit_order(partial_order)
                                    if fill.filled_quantity > 0:
                                        pos.quantity -= fill.filled_quantity
                                        logger.info(
                                            "Partial close %s: sold %.6f, remaining %.6f",
                                            pos.symbol, fill.filled_quantity, pos.quantity,
                                        )
                                except Exception as e:
                                    logger.error("Partial close failed for %s: %s", review.symbol, e)
                        await self.emit_event("partial_take", {
                            "symbol": review.symbol,
                            "pct": review.partial_close_pct,
                            "reasoning": review.reasoning[:200],
                        })
            except Exception as e:
                logger.error("Position Manager failed: %s", e, exc_info=True)

        # ── Step 5c: Cancel stale orders ─────────────────────
        try:
            cancelled = await self.exchange.cancel_stale_orders(max_age_minutes=30)
            if cancelled:
                await self.emit_event("stale_orders_cancelled", {"count": len(cancelled)})
        except Exception as e:
            logger.warning("Stale order cancellation failed: %s", e)

        # ── Step 6: Bull/Bear Debate ─────────────────────────
        debate_summary = None
        try:
            debate_summary = await run_debate(
                bull=self.bull_researcher,
                bear=self.bear_researcher,
                analyst_briefs=briefs,
            )
            await self.emit_event("debate_complete", {
                "consensus": debate_summary.consensus_direction,
                "agreement": debate_summary.agreement_level,
                "bull_conviction": debate_summary.bull_argument.conviction,
                "bear_conviction": debate_summary.bear_argument.conviction,
            })
        except Exception as e:
            logger.warning("Debate failed (continuing without): %s", e)

        # ── Step 7: Strategist ───────────────────────────────
        current_prices = {}
        for symbol, snap in snapshots.items():
            if snap.ticker:
                current_prices[symbol] = {
                    "last": snap.ticker.last,
                    "bid": snap.ticker.bid,
                    "ask": snap.ticker.ask,
                    "volume_24h": snap.ticker.volume_24h,
                }

        playbook = self.semantic.get_playbook()
        strategy_context = {
            "analyst_briefs": [b.model_dump(mode="json") for b in briefs],
            "playbook": playbook,
            "current_positions": positions,
            "portfolio_value": portfolio_value,
            "current_prices": current_prices,
        }
        if debate_summary:
            strategy_context["debate_summary"] = debate_summary.model_dump(mode="json")

        decision = await self.strategist.invoke(strategy_context, StrategyDecision)
        await self.emit_event("strategy_decision", {
            "regime": decision.market_regime.value,
            "action": decision.proposed_action.value,
            "symbol": decision.symbol,
            "conviction": decision.conviction_score,
            "reasoning": decision.reasoning[:300],
        })

        # ── Step 7: Patience Engine ──────────────────────────
        allowed, reason = self.patience.should_proceed(decision)
        if not allowed:
            logger.info("Patience Engine: %s", reason)
            await self.emit_event("patience_block", {"reason": reason})
            await self._record_cycle(cycle, briefs, decision, None, "hold", reason)
            self.working.save_to_disk()
            return {"cycle": cycle, "action": "hold", "reason": reason}

        # ── Step 8: Risk Manager ─────────────────────────────
        risk_context = {
            "strategy_decision": decision.model_dump(mode="json"),
            "risk_limits": self.settings.risk.model_dump(),
            "current_positions": positions,
            "portfolio_value": portfolio_value,
            "current_drawdown_pct": self.working.current_drawdown_pct,
            "trades_today": self.patience.state.trades_today,
        }
        risk_result = await self.risk_manager.invoke(risk_context, RiskAssessment)
        await self.emit_event("risk_assessment", {
            "decision": risk_result.decision.value,
            "reasoning": risk_result.reasoning[:300],
            "veto_reasons": risk_result.veto_reasons,
        })

        if risk_result.decision == RiskDecision.VETOED:
            logger.info("Risk Manager VETOED: %s", risk_result.veto_reasons)
            await self._record_cycle(
                cycle, briefs, decision, risk_result.model_dump(mode="json"),
                "vetoed", "; ".join(risk_result.veto_reasons),
            )
            self.working.save_to_disk()
            return {"cycle": cycle, "action": "vetoed", "reasons": risk_result.veto_reasons}

        # ── Step 9: Execute ──────────────────────────────────
        fill = await self.executor.execute(risk_result)
        if fill and fill.status.value == "filled":
            self.patience.record_trade()
            await self.emit_event("trade_executed", {
                "symbol": fill.symbol,
                "side": fill.side.value,
                "quantity": fill.filled_quantity,
                "price": fill.average_fill_price,
            })

            trade_id = await self.episodic.record_trade_open(
                symbol=fill.symbol,
                side=fill.side.value,
                entry_price=fill.average_fill_price,
                quantity=fill.filled_quantity,
                analyst_briefs=[b.model_dump(mode="json") for b in briefs],
                strategy_decision=decision.model_dump(mode="json"),
                risk_assessment=risk_result.model_dump(mode="json"),
            )

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
        return {
            "cycle": cycle,
            "action": "trade",
            "fill": fill.model_dump(mode="json") if fill else None,
        }

    # ── Position Exit Monitoring ────────────────────────────

    async def _check_position_exits(self, live_positions: list[dict]) -> None:
        """Check if any open positions should be closed (stop-loss or take-profit hit).

        Compares current prices against stored stop/target levels.
        When a position is closed, triggers the Auditor for post-mortem.
        """
        live_by_symbol = {p["symbol"]: p for p in live_positions}

        for symbol, pos in list(self.working.positions.items()):
            # Normalize symbol for matching (e.g. BTC/USD vs BTCUSD)
            live_key = symbol.replace("/", "")
            live = live_by_symbol.get(live_key) or live_by_symbol.get(symbol)

            if not live:
                # Position no longer exists on exchange — it was closed externally
                logger.info("Position %s no longer on exchange — recording close", symbol)
                await self._close_and_audit_position(pos, pos.entry_price, "closed_externally")
                continue

            current_price = live.get("current_price", 0)
            if current_price <= 0:
                continue

            # Check stop-loss
            if pos.stop_loss and current_price <= pos.stop_loss:
                logger.info(
                    "STOP-LOSS triggered for %s: price $%.2f <= stop $%.2f",
                    symbol, current_price, pos.stop_loss,
                )
                await self.emit_event("stop_loss_triggered", {
                    "symbol": symbol,
                    "price": current_price,
                    "stop": pos.stop_loss,
                })
                await self._close_and_audit_position(pos, current_price, "stop_loss")
                continue

            # Check take-profit
            if pos.take_profit and current_price >= pos.take_profit:
                logger.info(
                    "TAKE-PROFIT triggered for %s: price $%.2f >= target $%.2f",
                    symbol, current_price, pos.take_profit,
                )
                await self.emit_event("take_profit_triggered", {
                    "symbol": symbol,
                    "price": current_price,
                    "target": pos.take_profit,
                })
                await self._close_and_audit_position(pos, current_price, "take_profit")

    async def _close_and_audit_position(
        self, pos: Position, exit_price: float, exit_reason: str
    ) -> None:
        """Close a position on the exchange, record it, and run Auditor post-mortem."""
        from src.contracts import ExecutionOrder, OrderSide, OrderType

        # Submit a MARKET order to close the position on the exchange
        close_side = OrderSide.SELL if pos.side == "buy" else OrderSide.BUY
        close_order = ExecutionOrder(
            symbol=pos.symbol,
            side=close_side,
            order_type=OrderType.MARKET,
            quantity=pos.quantity,
        )
        try:
            fill = await self.exchange.submit_order(close_order)
            if fill.filled_quantity > 0:
                exit_price = fill.average_fill_price  # Use actual fill price
                logger.info(
                    "Closed %s on exchange: %s %.6f @ $%.2f",
                    pos.symbol, close_side.value, fill.filled_quantity, exit_price,
                )
            else:
                logger.warning(
                    "Close order for %s did not fill — status: %s",
                    pos.symbol, fill.status.value,
                )
        except Exception as e:
            logger.error("Failed to close %s on exchange: %s", pos.symbol, e)
            # Continue with memory cleanup even if exchange close fails
            # The position will be caught by recovery on next startup

        # PnL: long = (exit - entry), short = (entry - exit)
        if pos.side == "buy":
            pnl = (exit_price - pos.entry_price) * pos.quantity
        else:
            pnl = (pos.entry_price - exit_price) * pos.quantity
        cost_basis = pos.entry_price * pos.quantity
        pnl_pct = (pnl / cost_basis) * 100 if cost_basis > 0 else 0

        # Remove from working memory
        self.working.close_position(pos.symbol)

        await self.emit_event("position_closed", {
            "symbol": pos.symbol,
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "reason": exit_reason,
        })

        # ── Auditor post-mortem ──────────────────────────────
        hold_minutes = 0.0
        try:
            hold_minutes = (
                datetime.fromisoformat(datetime.utcnow().isoformat())
                - datetime.fromisoformat(pos.opened_at)
            ).total_seconds() / 60
        except Exception:
            pass

        post_mortem_dict = None
        try:
            audit_context = {
                "trade_data": {
                    "trade_id": pos.trade_id,
                    "symbol": pos.symbol,
                    "side": pos.side,
                    "entry_price": pos.entry_price,
                    "exit_price": exit_price,
                    "quantity": pos.quantity,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "exit_reason": exit_reason,
                    "hold_duration_minutes": hold_minutes,
                    "stop_loss": pos.stop_loss,
                    "take_profit": pos.take_profit,
                },
                "analyst_briefs": pos.analyst_briefs,
                "strategy_decision": pos.strategy_decision,
                "risk_assessment": pos.risk_assessment,
                "playbook": self.semantic.get_playbook(),
            }

            post_mortem = await self.auditor.invoke(audit_context, TradePostMortem)
            post_mortem_dict = post_mortem.model_dump(mode="json")

            # Apply playbook updates from Auditor
            if post_mortem.playbook_updates:
                self.semantic.apply_updates(post_mortem.playbook_updates)
                await self.emit_event("playbook_updated", {
                    "updates": len(post_mortem.playbook_updates),
                    "new_version": self.semantic.get_playbook().get("version", 0),
                })

            await self.emit_event("post_mortem", {
                "symbol": pos.symbol,
                "outcome": post_mortem.outcome.value,
                "pnl": pnl,
                "pattern_accuracy": post_mortem.pattern_accuracy,
                "lessons": post_mortem.lessons[:3],
            })

            logger.info(
                "Auditor post-mortem for %s: %s, P&L: $%.2f (%.1f%%)",
                pos.symbol, post_mortem.outcome.value, pnl, pnl_pct,
            )

        except Exception as e:
            logger.error("Auditor failed for %s: %s", pos.symbol, e, exc_info=True)
            await self.emit_event("agent_error", {"agent": "auditor", "error": str(e)})

        # Always record the close — even if auditor fails
        if pos.trade_id:
            await self.episodic.record_trade_close(
                trade_id=pos.trade_id,
                exit_price=exit_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                post_mortem=post_mortem_dict,
            )

    # ── Cycle Recording ─────────────────────────────────────

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

    # ── Continuous Loop ─────────────────────────────────────

    async def run(self) -> None:
        """Run the trading loop continuously."""
        self._running = True
        interval = self.settings.cycle.interval_minutes * 60
        logger.info(
            "Trading loop started — cycle every %d minutes", self.settings.cycle.interval_minutes
        )

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
