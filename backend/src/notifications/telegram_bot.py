"""Telegram bot integration for TradeBot.

Provides real-time trade notifications and remote command interface.
Uses python-telegram-bot v20+ (async) and integrates non-blockingly
with the existing FastAPI event loop.

Environment variables:
    TELEGRAM_BOT_TOKEN  -- Bot token from @BotFather
    TELEGRAM_CHAT_ID    -- Numeric chat ID of the authorized admin
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

_SIDE_LABEL = {"buy": "LONG", "sell": "SHORT"}


def _mono(value: Any) -> str:
    """Wrap a value in monospace backticks for Telegram Markdown."""
    return f"`{value}`"


def _sign(number: float) -> str:
    """Return a number string with explicit + for positive values."""
    if number >= 0:
        return f"+{number:,.2f}"
    return f"{number:,.2f}"


def _pct(number: float) -> str:
    """Format a percentage with sign."""
    if number >= 0:
        return f"+{number:.2f}%"
    return f"{number:.2f}%"


def _escape_md(text: str) -> str:
    """Escape characters that conflict with Markdown.

    We use plain Markdown (not V2) for simplicity, so only backticks
    inside user-supplied strings need escaping.
    """
    return text.replace("`", "'")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# TelegramNotifier
# ---------------------------------------------------------------------------


class TelegramNotifier:
    """Async Telegram bot that sends notifications and handles commands.

    Typical lifecycle::

        notifier = TelegramNotifier()
        await notifier.start()      # call once during FastAPI lifespan startup
        await notifier.notify("System online")
        ...
        await notifier.stop()       # call during shutdown
    """

    def __init__(
        self,
        token: str | None = None,
        chat_id: str | int | None = None,
        api_base_url: str = "http://127.0.0.1:8000",
    ) -> None:
        self._token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        raw_chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._chat_id: int = int(raw_chat_id) if raw_chat_id else 0
        self._api_base = api_base_url.rstrip("/")

        if not self._token:
            logger.warning("TELEGRAM_BOT_TOKEN not set -- Telegram notifier disabled")
        if not self._chat_id:
            logger.warning("TELEGRAM_CHAT_ID not set -- Telegram notifier disabled")

        self._enabled = bool(self._token and self._chat_id)
        self._app: Application | None = None
        self._bot: Bot | None = None
        self._http: httpx.AsyncClient | None = None
        self._started = False

    @property
    def enabled(self) -> bool:
        """True when valid credentials are present and the bot can operate."""
        return self._enabled

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Build the Application, register handlers, and start polling.

        Safe to call even when credentials are missing -- it simply no-ops.
        """
        if not self._enabled:
            logger.info("Telegram notifier is disabled (missing credentials)")
            return

        self._http = httpx.AsyncClient(base_url=self._api_base, timeout=30.0)

        self._app = (
            Application.builder()
            .token(self._token)
            .build()
        )
        self._bot = self._app.bot

        # Register command handlers.
        # /start and /stop control the continuous trading loop.
        # /help shows available commands.
        handlers = [
            ("help", self._cmd_help),
            ("status", self._cmd_status),
            ("positions", self._cmd_positions),
            ("balance", self._cmd_balance),
            ("playbook", self._cmd_playbook),
            ("cycle", self._cmd_cycle),
            ("start", self._cmd_start),
            ("stop", self._cmd_stop),
        ]
        for name, callback in handlers:
            self._app.add_handler(CommandHandler(name, callback))

        # Initialize and start polling in the background.  We use
        # initialize() + start() + updater.start_polling() rather than
        # Application.run_polling() so we do not block the FastAPI event loop.
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)

        self._started = True
        logger.info("Telegram bot started -- polling for commands")

    async def stop(self) -> None:
        """Gracefully shut down the bot and HTTP client."""
        if self._app and self._started:
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
            except Exception:
                logger.debug("Telegram shutdown warning (non-critical)", exc_info=True)
            self._started = False

        if self._http:
            await self._http.aclose()
            self._http = None

        logger.info("Telegram bot stopped")

    # ------------------------------------------------------------------
    # Authorization guard
    # ------------------------------------------------------------------

    def _is_authorized(self, update: Update) -> bool:
        """Return True if the message comes from the admin chat."""
        if not update.effective_chat:
            return False
        return update.effective_chat.id == self._chat_id

    async def _guard(self, update: Update) -> bool:
        """Check authorization; send a rejection if unauthorized.

        Returns True if the caller IS authorized and may proceed.
        """
        if self._is_authorized(update):
            return True
        if update.effective_message:
            await update.effective_message.reply_text("Unauthorized.")
        return False

    # ------------------------------------------------------------------
    # Outbound notification methods (called by the trading system)
    # ------------------------------------------------------------------

    async def notify(self, message: str) -> None:
        """Send a plain-text message to the admin chat."""
        if not self._enabled or not self._bot:
            return
        try:
            await self._bot.send_message(
                chat_id=self._chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            logger.error("Failed to send Telegram message", exc_info=True)

    async def notify_trade(self, event: dict) -> None:
        """Format and send a trade execution notification.

        Expected keys: symbol, side, quantity, price, pnl (optional),
        pnl_pct (optional), reason (optional).
        """
        symbol = event.get("symbol", "???")
        side = event.get("side", "???")
        qty = event.get("quantity", event.get("filled_quantity", 0))
        price = event.get("price", event.get("average_fill_price", 0))
        label = _SIDE_LABEL.get(side, side.upper())

        lines = [
            "*Trade Executed*",
            "",
            f"Symbol:   {_mono(symbol)}",
            f"Side:     {_mono(label)}",
            f"Qty:      {_mono(f'{qty:,.6g}')}",
            f"Price:    {_mono(f'${price:,.2f}')}",
        ]

        pnl = event.get("pnl")
        pnl_pct = event.get("pnl_pct")
        if pnl is not None:
            lines.append(f"P&L:      {_mono(f'${_sign(pnl)}')}")
        if pnl_pct is not None:
            lines.append(f"P&L %:    {_mono(_pct(pnl_pct))}")

        reason = event.get("reason")
        if reason:
            lines.append(f"Reason:   {_escape_md(reason)}")

        lines.append(f"\n{_timestamp()}")
        await self.notify("\n".join(lines))

    async def notify_position_closed(self, event: dict) -> None:
        """Send a notification when a position is closed."""
        symbol = event.get("symbol", "???")
        exit_price = event.get("exit_price", 0)
        pnl = event.get("pnl", 0)
        pnl_pct = event.get("pnl_pct", 0)
        reason = event.get("reason", "unknown")
        outcome = "WIN" if pnl >= 0 else "LOSS"

        lines = [
            f"*Position Closed -- {outcome}*",
            "",
            f"Symbol:   {_mono(symbol)}",
            f"Exit:     {_mono(f'${exit_price:,.2f}')}",
            f"P&L:      {_mono(f'${_sign(pnl)}')}",
            f"P&L %:    {_mono(_pct(pnl_pct))}",
            f"Reason:   {_escape_md(reason)}",
            f"\n{_timestamp()}",
        ]
        await self.notify("\n".join(lines))

    async def notify_cycle_summary(self, event: dict) -> None:
        """Send a summary after a trading cycle completes.

        Expected keys: cycle, action, reason (optional), fill (optional).
        """
        cycle = event.get("cycle", "?")
        action = event.get("action", "unknown")
        reason = event.get("reason", "")

        lines = [
            f"*Cycle #{cycle} Complete*",
            "",
            f"Action:   {_mono(action.upper())}",
        ]

        if reason:
            lines.append(f"Reason:   {_escape_md(reason[:200])}")

        fill = event.get("fill")
        if fill and isinstance(fill, dict):
            lines.append(f"Symbol:   {_mono(fill.get('symbol', ''))}")
            avg_price = fill.get("average_fill_price", 0)
            lines.append(f"Price:    {_mono(f'${avg_price:,.2f}')}")

        lines.append(f"\n{_timestamp()}")
        await self.notify("\n".join(lines))

    async def notify_error(self, error: str) -> None:
        """Send an error alert to the admin chat."""
        text = f"*ERROR*\n\n{_escape_md(error[:1000])}\n\n{_timestamp()}"
        await self.notify(text)

    # ------------------------------------------------------------------
    # Command handlers (inbound from Telegram)
    # ------------------------------------------------------------------

    async def _cmd_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._guard(update):
            return
        text = (
            "*TradeBot Commands*\n"
            "\n"
            "/status      -- System health & cycle count\n"
            "/positions   -- Open positions\n"
            "/balance     -- Portfolio value & cash\n"
            "/playbook    -- Current trading playbook\n"
            "/cycle       -- Run one analysis cycle now\n"
            "/start       -- Start continuous trading\n"
            "/stop        -- Stop continuous trading\n"
            "/help        -- Show this message\n"
        )
        await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._guard(update):
            return
        data = await self._api_get("/api/health")
        if data is None:
            await update.effective_message.reply_text("Failed to reach backend.")
            return
        components = data.get("components", {})
        lines = [
            "*System Status*",
            "",
            f"Status:     {_mono(data.get('status', 'unknown'))}",
            f"Cycle:      {_mono(data.get('cycle', 0))}",
            f"Loop:       {_mono('active' if components.get('trading_loop') else 'inactive')}",
            f"Positions:  {_mono(components.get('positions', 0))}",
            f"\n{_timestamp()}",
        ]
        await update.effective_message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.MARKDOWN
        )

    async def _cmd_positions(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._guard(update):
            return
        data = await self._api_get("/api/positions")
        if data is None:
            await update.effective_message.reply_text("Failed to reach backend.")
            return
        if not data:
            await update.effective_message.reply_text("No open positions.")
            return

        lines = ["*Open Positions*", ""]
        for pos in data:
            symbol = pos.get("symbol", "???")
            side = pos.get("side", "???")
            qty = pos.get("qty", pos.get("quantity", 0))
            entry = pos.get("avg_entry_price", pos.get("entry_price", 0))
            current = pos.get("current_price", 0)
            unrealized = pos.get("unrealized_pl", pos.get("pnl", ""))
            lines.append(
                f"{_mono(symbol)} {_SIDE_LABEL.get(side, side.upper())}\n"
                f"  Qty: {_mono(qty)}  Entry: {_mono(f'${float(entry):,.2f}')}"
            )
            if current:
                lines.append(f"  Current: {_mono(f'${float(current):,.2f}')}")
            if unrealized != "":
                lines.append(f"  Unrealized P&L: {_mono(f'${float(unrealized):,.2f}')}")
            lines.append("")

        lines.append(_timestamp())
        await update.effective_message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.MARKDOWN
        )

    async def _cmd_balance(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._guard(update):
            return
        data = await self._api_get("/api/portfolio")
        if data is None:
            await update.effective_message.reply_text("Failed to reach backend.")
            return
        value = data.get("value", 0)
        cash = data.get("cash", 0)
        drawdown = data.get("drawdown_pct", 0)
        peak = data.get("peak_value", 0)
        risk = data.get("risk_pct", 0)
        lines = [
            "*Portfolio*",
            "",
            f"Value:      {_mono(f'${value:,.2f}')}",
            f"Cash:       {_mono(f'${cash:,.2f}')}",
            f"Peak:       {_mono(f'${peak:,.2f}')}",
            f"Drawdown:   {_mono(f'{drawdown:.2f}%')}",
            f"Risk:       {_mono(f'{risk:.2f}%')}",
            f"\n{_timestamp()}",
        ]
        await update.effective_message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.MARKDOWN
        )

    async def _cmd_playbook(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._guard(update):
            return
        data = await self._api_get("/api/playbook")
        if data is None:
            await update.effective_message.reply_text("Failed to reach backend.")
            return
        if not data:
            await update.effective_message.reply_text("Playbook is empty.")
            return

        # Render a compact summary of the playbook dict
        version = data.get("version", "?")
        rules = data.get("rules", [])
        lines = [f"*Playbook v{version}*", ""]

        if rules:
            for i, rule in enumerate(rules[:10], 1):
                if isinstance(rule, dict):
                    lines.append(f"{i}. {_escape_md(rule.get('text', str(rule))[:120])}")
                else:
                    lines.append(f"{i}. {_escape_md(str(rule)[:120])}")
        else:
            # Fallback: show top-level keys and their types
            for key, val in list(data.items())[:10]:
                if key == "version":
                    continue
                if isinstance(val, list):
                    lines.append(f"{key}: {_mono(f'{len(val)} items')}")
                elif isinstance(val, dict):
                    lines.append(f"{key}: {_mono(f'{len(val)} entries')}")
                else:
                    lines.append(f"{key}: {_mono(str(val)[:80])}")

        lines.append(f"\n{_timestamp()}")
        await update.effective_message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.MARKDOWN
        )

    async def _cmd_cycle(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._guard(update):
            return
        await update.effective_message.reply_text("Running one analysis cycle ...")
        data = await self._api_post("/api/run-cycle")
        if data is None:
            await update.effective_message.reply_text("Cycle failed -- check server logs.")
            return

        action = data.get("action", "unknown")
        cycle = data.get("cycle", "?")
        reason = data.get("reason", "")
        lines = [
            f"*Cycle #{cycle} Result*",
            "",
            f"Action: {_mono(action.upper())}",
        ]
        if reason:
            lines.append(f"Reason: {_escape_md(reason[:200])}")

        fill = data.get("fill")
        if fill and isinstance(fill, dict):
            avg_price = fill.get("average_fill_price", 0)
            lines.append(f"Fill: {_mono(fill.get('symbol', ''))} "
                         f"@ {_mono(f'${avg_price:,.2f}')}")

        lines.append(f"\n{_timestamp()}")
        await update.effective_message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.MARKDOWN
        )

    async def _cmd_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._guard(update):
            return
        data = await self._api_post("/api/start")
        if data is None:
            await update.effective_message.reply_text("Failed to reach backend.")
            return
        status = data.get("status", "unknown")
        await update.effective_message.reply_text(
            f"Trading loop: {_mono(status)}", parse_mode=ParseMode.MARKDOWN
        )

    async def _cmd_stop(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._guard(update):
            return
        data = await self._api_post("/api/stop")
        if data is None:
            await update.effective_message.reply_text("Failed to reach backend.")
            return
        status = data.get("status", "unknown")
        await update.effective_message.reply_text(
            f"Trading loop: {_mono(status)}", parse_mode=ParseMode.MARKDOWN
        )

    # ------------------------------------------------------------------
    # Internal HTTP helpers (call FastAPI endpoints)
    # ------------------------------------------------------------------

    async def _api_get(self, path: str) -> dict | list | None:
        """GET a JSON endpoint from the FastAPI backend."""
        if not self._http:
            return None
        try:
            resp = await self._http.get(path)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.error("Telegram->API GET %s failed", path, exc_info=True)
            return None

    async def _api_post(self, path: str, json_body: dict | None = None) -> dict | None:
        """POST to a JSON endpoint on the FastAPI backend."""
        if not self._http:
            return None
        try:
            resp = await self._http.post(path, json=json_body)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.error("Telegram->API POST %s failed", path, exc_info=True)
            return None
