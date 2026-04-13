"""FastAPI backend — REST + WebSocket endpoints for the dashboard.

Serves market data, agent reasoning streams, trade history, and config.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import load_settings
from src.core.trading_loop import TradingLoop
from src.data.market_data import MarketDataProvider
from src.exchange.paper import AlpacaPaperExchange
from src.llm.claude_provider import ClaudeProvider
from src.llm.grok_provider import GrokProvider
from src.memory.episodic import EpisodicMemory
from src.memory.semantic import SemanticMemory
from src.memory.working import WorkingMemory
from src.notifications.telegram_bot import TelegramNotifier

logger = logging.getLogger(__name__)

# Global state
_trading_loop: TradingLoop | None = None
_telegram: TelegramNotifier | None = None
_ws_clients: set[WebSocket] = set()
_working_memory = WorkingMemory()

# Event types that trigger Telegram notifications
_TRADE_EVENTS = {"trade_executed"}
_CLOSE_EVENTS = {"position_closed"}
_CYCLE_EVENTS = {"cycle_start"}
_ERROR_EVENTS = {"cycle_error", "agent_error"}


async def broadcast_event(event: dict) -> None:
    """Broadcast an event to all connected WebSocket clients and Telegram."""
    message = json.dumps(event, default=str)
    disconnected = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    _ws_clients -= disconnected

    # Forward relevant events to Telegram (fire-and-forget)
    if _telegram and _telegram.enabled:
        event_type = event.get("type", "")
        try:
            if event_type in _TRADE_EVENTS:
                await _telegram.notify_trade(event)
            elif event_type in _CLOSE_EVENTS:
                await _telegram.notify_position_closed(event)
            elif event_type in _ERROR_EVENTS:
                await _telegram.notify_error(
                    f"[{event_type}] {event.get('error', 'unknown')}"
                )
        except Exception:
            logger.debug("Telegram notification failed (non-critical)", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    global _trading_loop, _telegram

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    logger.info("TradeBot starting up...")

    _loop_task = None

    try:
        settings = load_settings()

        # Initialize components — each wrapped individually so one failure
        # doesn't prevent the rest from starting
        market_data = None
        exchange = None
        claude = None
        grok = None
        episodic = None
        semantic = SemanticMemory()

        try:
            semantic.load()
        except Exception as e:
            logger.warning("Playbook load failed: %s", e)

        try:
            market_data = MarketDataProvider(settings.exchange.name, sandbox=True)
            await market_data.initialize()
        except Exception as e:
            logger.warning("Market data init failed: %s", e)
            market_data = None

        try:
            exchange = AlpacaPaperExchange(paper=True)
            await exchange.initialize()
        except Exception as e:
            logger.warning("Exchange init failed: %s", e)
            exchange = None

        try:
            claude = ClaudeProvider(model=settings.llm.claude.model)
        except Exception as e:
            logger.warning("Claude init failed: %s", e)

        try:
            grok = GrokProvider(model=settings.llm.grok.model)
        except Exception as e:
            logger.warning("Grok init failed: %s", e)

        try:
            episodic = EpisodicMemory(settings.database.url)
            await episodic.initialize()
        except Exception as e:
            logger.warning("Database init failed: %s", e)
            episodic = None

        _working_memory.load_from_disk()

        # Only create trading loop if we have the minimum required components
        if market_data and exchange and claude and episodic:
            _trading_loop = TradingLoop(
                settings=settings,
                market_data=market_data,
                exchange=exchange,
                claude_llm=claude,
                grok_llm=grok,
                working_memory=_working_memory,
                episodic_memory=episodic,
                semantic_memory=semantic,
                event_callback=broadcast_event,
            )

            # Crash recovery
            try:
                from src.core.recovery import RecoveryManager
                recovery = RecoveryManager()
                report = await recovery.recover(_working_memory, exchange)
                if report.actions_taken:
                    logger.info("Recovery: %s", "; ".join(report.actions_taken))
            except Exception as e:
                logger.warning("Recovery failed: %s", e)

            # Auto-start trading loop
            _loop_task = asyncio.create_task(_trading_loop.run())
            logger.info("Trading loop auto-started")
        else:
            logger.warning(
                "Trading loop NOT started — missing components: "
                "market_data=%s exchange=%s claude=%s db=%s",
                market_data is not None, exchange is not None,
                claude is not None, episodic is not None,
            )

        # Telegram bot (optional)
        try:
            _telegram = TelegramNotifier(
                api_base_url=f"http://127.0.0.1:{settings.dashboard.port}",
            )
            await _telegram.start()
        except Exception as e:
            logger.warning("Telegram not started: %s", e)
            _telegram = None

    except Exception as e:
        logger.error("Startup error (app will still serve health endpoint): %s", e, exc_info=True)

    logger.info("TradeBot backend ready")
    yield

    # Shutdown
    if _loop_task:
        _loop_task.cancel()
        try:
            await _loop_task
        except asyncio.CancelledError:
            pass
    if _telegram:
        try:
            await _telegram.stop()
        except Exception:
            pass
    if _trading_loop:
        _trading_loop.stop()
        try:
            await _trading_loop.market_data.close()
            await _trading_loop.exchange.close()
            await _trading_loop._claude.close()
            if _trading_loop._grok:
                await _trading_loop._grok.close()
            await _trading_loop.episodic.close()
        except Exception:
            pass
    from src.data.external_sources import close_client as close_http_client
    await close_http_client()


app = FastAPI(
    title="TradeBot — Multi-Agent Trading Floor",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST Endpoints ───────────────────────────────────────────────

@app.get("/api/health")
async def health():
    components = {
        "trading_loop": _trading_loop is not None,
        "positions": len(_working_memory.positions),
    }
    return {
        "status": "ok" if _trading_loop else "degraded",
        "cycle": _working_memory.cycle_count,
        "components": components,
    }


@app.get("/api/portfolio")
async def get_portfolio():
    # Calculate portfolio risk: sum of (position_value / portfolio * distance_to_stop)
    risk_pct = 0.0
    pv = _working_memory.portfolio_value
    if pv > 0:
        for pos in _working_memory.positions.values():
            pos_value = pos.entry_price * pos.quantity
            if pos.stop_loss and pos.entry_price > 0:
                stop_distance = abs(pos.entry_price - pos.stop_loss) / pos.entry_price
                risk_pct += (pos_value / pv) * stop_distance * 100
            else:
                # No stop-loss = full position at risk
                risk_pct += (pos_value / pv) * 100

    return {
        "value": _working_memory.portfolio_value,
        "cash": _working_memory.cash_balance,
        "drawdown_pct": _working_memory.current_drawdown_pct,
        "peak_value": _working_memory.peak_portfolio_value,
        "risk_pct": round(risk_pct, 2),
        "positions": {k: vars(v) for k, v in _working_memory.positions.items()},
    }


@app.get("/api/positions")
async def get_positions():
    if _trading_loop:
        return await _trading_loop.exchange.get_positions()
    return []


@app.get("/api/trades")
async def get_trades():
    if _trading_loop:
        return await _trading_loop.episodic.get_recent_trades()
    return []


@app.get("/api/playbook")
async def get_playbook():
    if _trading_loop:
        return _trading_loop.semantic.get_playbook()
    return {}


@app.get("/api/agent-logs")
async def get_agent_logs():
    return _working_memory.agent_logs[-50:]


@app.get("/api/candles/{symbol}/{timeframe}")
async def get_candles(symbol: str, timeframe: str, limit: int = 200):
    """Fetch OHLCV candle data for dashboard charts."""
    if not _trading_loop:
        return []
    # URL-decode symbol: BTC-USD -> BTC/USD
    decoded_symbol = symbol.replace("-", "/")
    candles = await _trading_loop.market_data.fetch_candles(
        decoded_symbol, timeframe, limit=limit, drop_incomplete=True,
    )
    return [
        {
            "time": int(c.timestamp.timestamp()),
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in candles
    ]


@app.get("/api/trades/markers")
async def get_trade_markers():
    """Get trade entry/exit points for chart overlay."""
    if not _trading_loop:
        return []
    trades = await _trading_loop.episodic.get_recent_trades(limit=50)
    markers = []
    for t in trades:
        if t.get("opened_at"):
            markers.append({
                "time": t["opened_at"],
                "symbol": t["symbol"],
                "type": "entry",
                "side": t["side"],
                "price": t["entry_price"],
            })
        if t.get("closed_at") and t.get("exit_price"):
            markers.append({
                "time": t["closed_at"],
                "symbol": t["symbol"],
                "type": "exit",
                "price": t["exit_price"],
                "pnl": t.get("pnl"),
            })
    return markers


@app.get("/api/config")
async def get_config():
    settings = load_settings()
    return settings.model_dump()


@app.get("/api/stats")
async def get_stats():
    """Trading performance statistics."""
    if _trading_loop:
        try:
            return await _trading_loop.episodic.get_trade_stats()
        except Exception as e:
            logger.error("Failed to fetch trade stats: %s", e)
    return {
        "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
        "win_rate": 0.0, "total_pnl": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
        "largest_win": 0.0, "largest_loss": 0.0, "profit_factor": 0.0,
        "avg_hold_minutes": 0.0, "open_trades": 0,
    }


@app.get("/api/equity-curve")
async def get_equity_curve():
    """Cumulative P&L over time."""
    if _trading_loop:
        try:
            return await _trading_loop.episodic.get_equity_curve()
        except Exception as e:
            logger.error("Failed to fetch equity curve: %s", e)
    return []


@app.get("/api/cycle-stats")
async def get_cycle_stats():
    """Analysis cycle statistics (trades/holds/vetoes/errors)."""
    if _trading_loop:
        try:
            return await _trading_loop.episodic.get_cycle_stats()
        except Exception as e:
            logger.error("Failed to fetch cycle stats: %s", e)
    return {
        "total_cycles": 0, "trades_made": 0, "holds": 0,
        "vetoed": 0, "errors": 0, "recent_regimes": [],
    }


@app.get("/api/recent-cycles")
async def get_recent_cycles():
    """Recent analysis cycle summaries."""
    if _trading_loop:
        try:
            return await _trading_loop.episodic.get_recent_cycles()
        except Exception as e:
            logger.error("Failed to fetch recent cycles: %s", e)
    return []


@app.post("/api/run-cycle")
async def run_single_cycle():
    """Manually trigger one analysis cycle."""
    if _trading_loop:
        result = await _trading_loop.run_cycle()
        return result
    return {"error": "Trading loop not initialized"}


@app.post("/api/start")
async def start_loop():
    """Start the continuous trading loop."""
    if _trading_loop and not _trading_loop._running:
        asyncio.create_task(_trading_loop.run())
        return {"status": "started"}
    return {"status": "already_running"}


@app.post("/api/stop")
async def stop_loop():
    """Stop the continuous trading loop."""
    if _trading_loop:
        _trading_loop.stop()
        return {"status": "stopped"}
    return {"status": "not_running"}


# ── WebSocket Endpoints ──────────────────────────────────────────

@app.websocket("/ws/agent-feed")
async def ws_agent_feed(websocket: WebSocket):
    """Stream agent reasoning events to the dashboard in real-time."""
    await websocket.accept()
    _ws_clients.add(websocket)
    logger.info("Dashboard client connected (%d total)", len(_ws_clients))

    try:
        # Send recent logs on connect
        for log in _working_memory.agent_logs[-20:]:
            await websocket.send_text(json.dumps(log, default=str))

        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(websocket)
        logger.info("Dashboard client disconnected (%d remaining)", len(_ws_clients))


@app.websocket("/ws/market-data")
async def ws_market_data(websocket: WebSocket):
    """Stream live ticker updates for dashboard price display."""
    await websocket.accept()

    try:
        while True:
            if _trading_loop:
                settings = _trading_loop.settings
                for symbol in settings.exchange.symbols:
                    ticker = await _trading_loop.market_data.fetch_ticker(symbol)
                    if ticker:
                        await websocket.send_text(json.dumps({
                            "type": "ticker",
                            "symbol": ticker.symbol,
                            "bid": ticker.bid,
                            "ask": ticker.ask,
                            "last": ticker.last,
                            "volume": ticker.volume_24h,
                            "timestamp": ticker.timestamp.isoformat(),
                        }, default=str))

                    # Also send latest candle for real-time chart update
                    candles = await _trading_loop.market_data.fetch_candles(
                        symbol, "1m", limit=2, drop_incomplete=False,
                    )
                    if candles:
                        c = candles[-1]
                        await websocket.send_text(json.dumps({
                            "type": "candle",
                            "symbol": symbol,
                            "time": int(c.timestamp.timestamp()),
                            "open": c.open,
                            "high": c.high,
                            "low": c.low,
                            "close": c.close,
                            "volume": c.volume,
                        }, default=str))

            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
