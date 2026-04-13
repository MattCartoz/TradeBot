"""Chart rendering for AI vision — generates candlestick PNGs for LLM analysis."""

from __future__ import annotations

import base64
import io
import logging

import mplfinance as mpf
import pandas as pd

from .data_models import Candle

logger = logging.getLogger(__name__)

# Dark style matching a professional trading terminal
CHART_STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    marketcolors=mpf.make_marketcolors(
        up="#00c853",
        down="#ff1744",
        edge="inherit",
        wick="inherit",
        volume="in",
        ohlc="i",
    ),
    figcolor="#0d1117",
    facecolor="#0d1117",
    gridcolor="#1e2430",
    gridstyle="--",
    gridaxis="both",
)


class ChartRenderer:
    """Renders candlestick charts as PNG images for multimodal LLM analysis."""

    def render(
        self,
        candles: list[Candle],
        symbol: str,
        timeframe: str,
        show_volume: bool = True,
        show_ema: bool = True,
        show_bbands: bool = True,
    ) -> bytes:
        """Render a candlestick chart as PNG bytes.

        These images are sent to vision-capable LLMs (Claude, GPT-4o)
        so the AI can visually identify patterns — just like a human
        trader looking at their screen.
        """
        if len(candles) < 10:
            raise ValueError(f"Need at least 10 candles, got {len(candles)}")

        df = pd.DataFrame([c.model_dump() for c in candles])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
        df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})

        addplots = []

        if show_ema and len(df) >= 20:
            ema20 = df["Close"].ewm(span=20).mean()
            ema50 = df["Close"].ewm(span=50).mean()
            addplots.append(mpf.make_addplot(ema20, color="#2196f3", width=1.0))
            if len(df) >= 50:
                addplots.append(mpf.make_addplot(ema50, color="#ff9800", width=1.0))

        if show_bbands and len(df) >= 20:
            sma = df["Close"].rolling(20).mean()
            std = df["Close"].rolling(20).std()
            bb_upper = sma + 2 * std
            bb_lower = sma - 2 * std
            addplots.append(mpf.make_addplot(bb_upper, color="#7c4dff", width=0.7, linestyle="--"))
            addplots.append(mpf.make_addplot(bb_lower, color="#7c4dff", width=0.7, linestyle="--"))

        buf = io.BytesIO()
        mpf.plot(
            df,
            type="candle",
            style=CHART_STYLE,
            title=f"\n{symbol} — {timeframe}",
            volume=show_volume,
            addplot=addplots if addplots else None,
            figsize=(14, 8),
            tight_layout=True,
            savefig=dict(fname=buf, dpi=120, bbox_inches="tight"),
        )
        buf.seek(0)
        png_bytes = buf.read()
        logger.info("Rendered chart for %s %s (%d bytes)", symbol, timeframe, len(png_bytes))
        return png_bytes

    def render_base64(
        self,
        candles: list[Candle],
        symbol: str,
        timeframe: str,
        **kwargs,
    ) -> str:
        """Render chart and return as base64 string for LLM vision API."""
        png_bytes = self.render(candles, symbol, timeframe, **kwargs)
        return base64.b64encode(png_bytes).decode("utf-8")
