"""Technical indicator computation — deterministic math, not AI judgment."""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from .data_models import Candle, IndicatorValues


def compute_indicators(candles: list[Candle], symbol: str, timeframe: str) -> IndicatorValues:
    """Compute all technical indicators from OHLCV candles.

    Uses pandas-ta for deterministic calculations. The AI decides what
    these values MEAN — we just compute the math.
    """
    if len(candles) < 50:
        return IndicatorValues(symbol=symbol, timeframe=timeframe)

    df = pd.DataFrame([c.model_dump() for c in candles])
    df.set_index("timestamp", inplace=True)

    result = IndicatorValues(symbol=symbol, timeframe=timeframe)

    # Trend — Exponential & Simple Moving Averages
    ema20 = ta.ema(df["close"], length=20)
    ema50 = ta.ema(df["close"], length=50)
    if ema20 is not None and len(ema20) > 0:
        result.ema_20 = float(ema20.iloc[-1])
    if ema50 is not None and len(ema50) > 0:
        result.ema_50 = float(ema50.iloc[-1])

    sma200 = ta.sma(df["close"], length=200)
    if sma200 is not None and len(sma200.dropna()) > 0:
        result.sma_200 = float(sma200.dropna().iloc[-1])

    # Momentum — RSI
    rsi = ta.rsi(df["close"], length=14)
    if rsi is not None and len(rsi.dropna()) > 0:
        result.rsi_14 = float(rsi.dropna().iloc[-1])

    # Momentum — MACD
    macd_df = ta.macd(df["close"])
    if macd_df is not None and len(macd_df.dropna()) > 0:
        last = macd_df.dropna().iloc[-1]
        result.macd_line = float(last.iloc[0])
        result.macd_histogram = float(last.iloc[1])
        result.macd_signal = float(last.iloc[2])

    # Volatility — Bollinger Bands
    bb_df = ta.bbands(df["close"], length=20, std=2.0)
    if bb_df is not None and len(bb_df.dropna()) > 0:
        last = bb_df.dropna().iloc[-1]
        result.bb_lower = float(last.iloc[0])
        result.bb_middle = float(last.iloc[1])
        result.bb_upper = float(last.iloc[2])

    # Volatility — ATR
    atr = ta.atr(df["high"], df["low"], df["close"], length=14)
    if atr is not None and len(atr.dropna()) > 0:
        result.atr_14 = float(atr.dropna().iloc[-1])

    # Volume — OBV
    obv = ta.obv(df["close"], df["volume"])
    if obv is not None and len(obv.dropna()) > 0:
        result.obv = float(obv.dropna().iloc[-1])

    # Volume — SMA of volume
    vol_sma = ta.sma(df["volume"], length=20)
    if vol_sma is not None and len(vol_sma.dropna()) > 0:
        result.volume_sma_20 = float(vol_sma.dropna().iloc[-1])

    # Trend Strength — ADX
    adx_df = ta.adx(df["high"], df["low"], df["close"], length=14)
    if adx_df is not None and len(adx_df.dropna()) > 0:
        result.adx_14 = float(adx_df.dropna().iloc[-1].iloc[0])

    return result
