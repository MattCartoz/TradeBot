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


class OrderBookLevel(BaseModel):
    """Single price level in the order book."""

    price: float
    volume: float


class OrderBook(BaseModel):
    """Order book depth snapshot."""

    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)

    def to_summary(self) -> str:
        """Human-readable summary for LLM context."""
        lines = [f"Order Book for {self.symbol}:"]
        if self.bids:
            total_bid_vol = sum(b.volume for b in self.bids)
            top_bid = self.bids[0]
            lines.append(f"  Best bid: ${top_bid.price:,.2f} (qty: {top_bid.volume:.4f})")
            lines.append(f"  Total bid depth ({len(self.bids)} levels): {total_bid_vol:.4f}")
            # Identify large bid walls
            avg_vol = total_bid_vol / len(self.bids) if self.bids else 0
            walls = [b for b in self.bids if b.volume > avg_vol * 3]
            if walls:
                lines.append(f"  Large bid walls at: {', '.join(f'${w.price:,.2f} ({w.volume:.4f})' for w in walls[:3])}")
        if self.asks:
            total_ask_vol = sum(a.volume for a in self.asks)
            top_ask = self.asks[0]
            lines.append(f"  Best ask: ${top_ask.price:,.2f} (qty: {top_ask.volume:.4f})")
            lines.append(f"  Total ask depth ({len(self.asks)} levels): {total_ask_vol:.4f}")
            walls = [a for a in self.asks if a.volume > (total_ask_vol / len(self.asks)) * 3]
            if walls:
                lines.append(f"  Large ask walls at: {', '.join(f'${w.price:,.2f} ({w.volume:.4f})' for w in walls[:3])}")
        if self.bids and self.asks:
            bid_vol = sum(b.volume for b in self.bids)
            ask_vol = sum(a.volume for a in self.asks)
            imbalance = bid_vol / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0.5
            bias = "BUY pressure" if imbalance > 0.55 else "SELL pressure" if imbalance < 0.45 else "balanced"
            lines.append(f"  Bid/Ask imbalance: {imbalance:.2f} ({bias})")
        return "\n".join(lines)


class MarketSnapshot(BaseModel):
    """Complete market data package for one symbol, multiple timeframes."""

    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ticker: Ticker | None = None
    candles: dict[str, list[Candle]] = Field(
        default_factory=dict,
        description="Keyed by timeframe, e.g. {'1h': [...], '4h': [...]}",
    )
    order_book: OrderBook | None = None


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
            lines.append(
                f"  MACD Line: {self.macd_line:.2f} / Signal: {self.macd_signal:.2f} "
                f"/ Histogram: {self.macd_histogram:.2f}"
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
            lines.append(f"  ADX(14): {self.adx_14:.1f}")
        return "\n".join(lines)
