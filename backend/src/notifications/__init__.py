"""Notification integrations for TradeBot.

Provides Telegram bot integration for real-time trade alerts and remote control.
"""

from .telegram_bot import TelegramNotifier

__all__ = ["TelegramNotifier"]
