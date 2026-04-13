"""Chart rendering for AI vision — generates multi-panel candlestick PNGs.

Produces professional-grade chart images that are sent to vision-capable
LLMs (Claude, GPT-4o). The AI looks at these charts the same way a
human trader looks at their TradingView screen — with RSI, MACD, volume,
and overlays all visible at once.
"""

from __future__ import annotations

import base64
import io
import logging

import mplfinance as mpf
import pandas as pd

from .data_models import Candle

logger = logging.getLogger(__name__)

CHART_STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    marketcolors=mpf.make_marketcolors(
        up="#30d158",
        down="#ff453a",
        edge="inherit",
        wick="inherit",
        volume="in",
        ohlc="i",
    ),
    figcolor="#000000",
    facecolor="#000000",
    gridcolor="rgba(255,255,255,0.04)",
    gridstyle="-",
    gridaxis="both",
    y_on_right=True,
)


class ChartRenderer:
    """Renders multi-panel candlestick charts for AI vision analysis."""

    def render(
        self,
        candles: list[Candle],
        symbol: str,
        timeframe: str,
        show_volume: bool = True,
        show_ema: bool = True,
        show_bbands: bool = True,
        show_vwap: bool = True,
        show_rsi: bool = True,
        show_macd: bool = True,
    ) -> bytes:
        """Render a multi-panel chart as PNG bytes.

        Panels:
        - Main: Candlesticks + EMA 20/50 + Bollinger Bands + VWAP
        - Volume: Colored by candle direction
        - RSI: 14-period with reference lines
        - MACD: Line + signal + histogram
        """
        if len(candles) < 20:
            raise ValueError(f"Need at least 20 candles, got {len(candles)}")

        df = pd.DataFrame([c.model_dump() for c in candles])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
        df = df.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        })

        addplots = []

        # EMA overlays on main chart
        if show_ema and len(df) >= 20:
            ema20 = df["Close"].ewm(span=20).mean()
            addplots.append(mpf.make_addplot(
                ema20, color="#0a84ff", width=1.0, label="EMA 20",
            ))
            if len(df) >= 50:
                ema50 = df["Close"].ewm(span=50).mean()
                addplots.append(mpf.make_addplot(
                    ema50, color="#ff9f0a", width=1.0, label="EMA 50",
                ))

        # Bollinger Bands
        if show_bbands and len(df) >= 20:
            sma = df["Close"].rolling(20).mean()
            std = df["Close"].rolling(20).std()
            bb_upper = sma + 2 * std
            bb_lower = sma - 2 * std
            addplots.append(mpf.make_addplot(
                bb_upper, color="#bf5af2", width=0.6, linestyle="--",
            ))
            addplots.append(mpf.make_addplot(
                bb_lower, color="#bf5af2", width=0.6, linestyle="--",
            ))

        # VWAP (Volume Weighted Average Price)
        if show_vwap and len(df) >= 10:
            typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
            vwap = (typical_price * df["Volume"]).cumsum() / df["Volume"].cumsum()
            addplots.append(mpf.make_addplot(
                vwap, color="#ffd60a", width=0.8, linestyle="-.",
            ))

        # RSI subplot
        if show_rsi and len(df) >= 15:
            delta = df["Close"].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, float("nan"))
            rsi = 100 - (100 / (1 + rs))

            addplots.append(mpf.make_addplot(
                rsi, panel=2, color="#0a84ff", width=0.8,
                ylabel="RSI",
            ))
            # Reference lines at 30 and 70
            rsi_30 = pd.Series(30, index=df.index)
            rsi_70 = pd.Series(70, index=df.index)
            addplots.append(mpf.make_addplot(
                rsi_30, panel=2, color="#6e6e73", width=0.4, linestyle="--",
            ))
            addplots.append(mpf.make_addplot(
                rsi_70, panel=2, color="#6e6e73", width=0.4, linestyle="--",
            ))

        # MACD subplot
        if show_macd and len(df) >= 26:
            ema12 = df["Close"].ewm(span=12).mean()
            ema26 = df["Close"].ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            histogram = macd_line - signal_line

            macd_panel = 3 if show_rsi else 2
            addplots.append(mpf.make_addplot(
                macd_line, panel=macd_panel, color="#0a84ff", width=0.8,
                ylabel="MACD",
            ))
            addplots.append(mpf.make_addplot(
                signal_line, panel=macd_panel, color="#ff9f0a", width=0.8,
            ))
            # Histogram colored by direction
            hist_pos = histogram.where(histogram >= 0, 0)
            hist_neg = histogram.where(histogram < 0, 0)
            addplots.append(mpf.make_addplot(
                hist_pos, panel=macd_panel, type="bar",
                color="#30d158", width=0.7, alpha=0.6,
            ))
            addplots.append(mpf.make_addplot(
                hist_neg, panel=macd_panel, type="bar",
                color="#ff453a", width=0.7, alpha=0.6,
            ))

        # Calculate panel ratios
        panel_ratios = [4, 1]  # Main + Volume
        if show_rsi:
            panel_ratios.append(1)
        if show_macd:
            panel_ratios.append(1)

        buf = io.BytesIO()
        mpf.plot(
            df,
            type="candle",
            style=CHART_STYLE,
            title=f"\n{symbol}  {timeframe}",
            volume=show_volume,
            addplot=addplots if addplots else None,
            figsize=(16, 10),
            panel_ratios=tuple(panel_ratios),
            tight_layout=True,
            savefig=dict(fname=buf, dpi=150, bbox_inches="tight"),
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
