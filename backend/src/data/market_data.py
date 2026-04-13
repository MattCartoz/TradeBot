"""Market data fetching via ccxt — OHLCV candles from exchanges."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import ccxt.async_support as ccxt

from .data_models import Candle, MarketSnapshot, Ticker

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """Fetches OHLCV and ticker data from exchanges via ccxt."""

    def __init__(self, exchange_name: str = "alpaca", sandbox: bool = True):
        exchange_class = getattr(ccxt, exchange_name, None)
        if exchange_class is None:
            raise ValueError(f"Unknown exchange: {exchange_name}")

        self._exchange: ccxt.Exchange = exchange_class({"sandbox": sandbox})
        self._exchange_name = exchange_name

    async def initialize(self) -> None:
        await self._exchange.load_markets()
        logger.info(
            "Loaded %d markets from %s", len(self._exchange.markets), self._exchange_name
        )

    async def close(self) -> None:
        await self._exchange.close()

    async def fetch_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[Candle]:
        """Fetch OHLCV candles for a symbol and timeframe."""
        try:
            ohlcv = await self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return [
                Candle(
                    timestamp=datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
                    open=row[1],
                    high=row[2],
                    low=row[3],
                    close=row[4],
                    volume=row[5],
                )
                for row in ohlcv
            ]
        except Exception as e:
            logger.error("Failed to fetch candles for %s %s: %s", symbol, timeframe, e)
            return []

    async def fetch_ticker(self, symbol: str) -> Ticker | None:
        """Fetch current price snapshot."""
        try:
            data = await self._exchange.fetch_ticker(symbol)
            return Ticker(
                symbol=symbol,
                bid=data.get("bid") or data.get("last", 0),
                ask=data.get("ask") or data.get("last", 0),
                last=data.get("last", 0),
                volume_24h=data.get("quoteVolume") or data.get("baseVolume", 0),
            )
        except Exception as e:
            logger.error("Failed to fetch ticker for %s: %s", symbol, e)
            return None

    async def fetch_snapshot(
        self, symbol: str, timeframes: list[str], candle_limit: int = 100
    ) -> MarketSnapshot:
        """Fetch complete market data for a symbol across all timeframes."""
        ticker = await self.fetch_ticker(symbol)
        candles: dict[str, list[Candle]] = {}

        for tf in timeframes:
            candles[tf] = await self.fetch_candles(symbol, tf, limit=candle_limit)

        return MarketSnapshot(symbol=symbol, ticker=ticker, candles=candles)
