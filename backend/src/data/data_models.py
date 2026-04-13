"""Market data models — Candle, Ticker, and related structures."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Candle(BaseModel):
    """Single OHLCV candlestick."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class Ticker(BaseModel):
    """Current price snapshot for a symbol."""

    symbol: str
    bid: float
    ask: float
    last: float
    volume_24h: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2


class MarketSnapshot(BaseModel):
    """Complete market data package for one symbol, multiple timeframes."""

    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ticker: Ticker | None = None
    candles: dict[str, list[Candle]] = Field(
        default_factory=dict,
        description="Keyed by timeframe, e.g. {'1h': [...], '4h': [...]}",
    )


class IndicatorValues(BaseModel):
    """Computed technical indicators for a symbol + timeframe."""

    symbol: str
    timeframe: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Trend
    ema_20: float | None = None
    ema_50: float | None = None
    sma_200: float | None = None

    # Momentum
    rsi_14: float | None = None
    macd_line: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None

    # Volatility
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    atr_14: float | None = None

    # Volume
    obv: float | None = None
    volume_sma_20: float | None = None

    # Trend strength
    adx_14: float | None = None

    def to_summary(self) -> str:
        """Human-readable summary for LLM context."""
        lines = [f"Indicators for {self.symbol} ({self.timeframe}):"]
        if self.rsi_14 is not None:
            lines.append(f"  RSI(14): {self.rsi_14:.1f}")
        if self.macd_line is not None:
            cross = "bullish" if (self.macd_histogram or 0) > 0 else "bearish"
            lines.append(
                f"  MACD: {self.macd_line:.2f} / Signal: {self.macd_signal:.2f} ({cross})"
            )
        if self.bb_upper is not None:
            lines.append(
                f"  Bollinger Bands: {self.bb_lower:.2f} / {self.bb_middle:.2f} / {self.bb_upper:.2f}"
            )
        if self.ema_20 is not None:
            lines.append(f"  EMA(20): {self.ema_20:.2f} | EMA(50): {self.ema_50:.2f}")
        if self.atr_14 is not None:
            lines.append(f"  ATR(14): {self.atr_14:.2f}")
        if self.adx_14 is not None:
            strength = "strong" if self.adx_14 > 25 else "weak"
            lines.append(f"  ADX(14): {self.adx_14:.1f} ({strength} trend)")
        return "\n".join(lines)
