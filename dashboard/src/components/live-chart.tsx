"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  ColorType,
  type CandlestickData,
  type Time,
} from "lightweight-charts";
import { useTheme } from "@/lib/theme";
import { API_URL, WS_URL, formatUSD } from "@/lib/utils";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1D"];
const SYMBOLS = ["BTC/USD", "ETH/USD"];

const THEMES = {
  dark: {
    bg: "#000000",
    text: "#6e6e73",
    grid: "rgba(255,255,255,0.03)",
    border: "rgba(255,255,255,0.06)",
    crosshair: "rgba(255,255,255,0.1)",
    labelBg: "#1c1c1e",
    up: "#30d158",
    down: "#ff453a",
    ema20: "#0a84ff",
    ema50: "#ff9f0a",
  },
  light: {
    bg: "#ffffff",
    text: "#86868b",
    grid: "rgba(0,0,0,0.03)",
    border: "rgba(0,0,0,0.06)",
    crosshair: "rgba(0,0,0,0.08)",
    labelBg: "#f5f5f7",
    up: "#28cd41",
    down: "#ff3b30",
    ema20: "#0071e3",
    ema50: "#ff9f0a",
  },
};

function computeEMA(data: CandlestickData<Time>[], period: number) {
  const k = 2 / (period + 1);
  const result: { time: Time; value: number }[] = [];
  let ema = 0;

  for (let i = 0; i < data.length; i++) {
    const close = data[i].close as number;
    if (i === 0) {
      ema = close;
    } else {
      ema = close * k + ema * (1 - k);
    }
    if (i >= period - 1) {
      result.push({ time: data[i].time, value: ema });
    }
  }
  return result;
}

export function LiveChart() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ema50Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const [activeTimeframe, setActiveTimeframe] = useState("1h");
  const [activeSymbol, setActiveSymbol] = useState("BTC/USD");
  const [livePrice, setLivePrice] = useState<number | null>(null);
  const [priceChange, setPriceChange] = useState<"up" | "down" | null>(null);
  const { theme } = useTheme();

  const fetchCandles = useCallback(
    async (sym: string, tf: string) => {
      try {
        const encodedSymbol = sym.replace("/", "-");
        const res = await fetch(
          `${API_URL}/api/candles/${encodedSymbol}/${tf}?limit=200`
        );
        if (!res.ok) return [];
        return (await res.json()) as CandlestickData<Time>[];
      } catch {
        return [];
      }
    },
    []
  );

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const t = THEMES[theme];
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: t.bg },
        textColor: t.text,
        fontFamily: "var(--font-geist-mono), monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: t.grid },
        horzLines: { color: t.grid },
      },
      crosshair: {
        vertLine: { color: t.crosshair, labelBackgroundColor: t.labelBg },
        horzLine: { color: t.crosshair, labelBackgroundColor: t.labelBg },
      },
      rightPriceScale: { borderColor: t.border },
      timeScale: { borderColor: t.border, timeVisible: true },
    });
    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: t.up,
      downColor: t.down,
      borderUpColor: t.up,
      borderDownColor: t.down,
      wickUpColor: t.up,
      wickDownColor: t.down,
    });
    candleSeriesRef.current = candleSeries;

    const ema20Series = chart.addSeries(LineSeries, {
      color: t.ema20,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ema20Ref.current = ema20Series;

    const ema50Series = chart.addSeries(LineSeries, {
      color: t.ema50,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ema50Ref.current = ema50Series;

    // Load initial data
    fetchCandles(activeSymbol, activeTimeframe).then((data) => {
      if (data.length > 0) {
        candleSeries.setData(data);
        ema20Series.setData(computeEMA(data, 20));
        ema50Series.setData(computeEMA(data, 50));
        chart.timeScale().fitContent();
        setLivePrice((data[data.length - 1].close as number) || null);
      }
    });

    // WebSocket for real-time updates
    const ws = new WebSocket(`${WS_URL}/ws/market-data`);
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "ticker" && msg.symbol === activeSymbol) {
          setLivePrice((prev) => {
            if (prev !== null) {
              setPriceChange(msg.last > prev ? "up" : msg.last < prev ? "down" : null);
            }
            return msg.last;
          });
        }
        if (msg.type === "candle" && msg.symbol === activeSymbol) {
          candleSeries.update({
            time: msg.time as Time,
            open: msg.open,
            high: msg.high,
            low: msg.low,
            close: msg.close,
          });
        }
      } catch {
        /* ignore */
      }
    };

    const ro = new ResizeObserver(() => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    });
    ro.observe(chartContainerRef.current);

    return () => {
      ws.close();
      ro.disconnect();
      chart.remove();
    };
  }, [theme, activeSymbol, activeTimeframe, fetchCandles]);

  // Handle symbol/timeframe changes
  const handleSymbolChange = (sym: string) => {
    setActiveSymbol(sym);
    setLivePrice(null);
  };

  const handleTimeframeChange = (tf: string) => {
    setActiveTimeframe(tf);
  };

  const t = THEMES[theme];

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3">
        <div className="flex items-center gap-4">
          <select
            value={activeSymbol}
            onChange={(e) => handleSymbolChange(e.target.value)}
            className="bg-transparent text-[13px] font-semibold text-text-primary font-mono appearance-none cursor-pointer pr-4"
          >
            {SYMBOLS.map((s) => (
              <option key={s} value={s}>
                {s.replace("/", " / ")}
              </option>
            ))}
          </select>
          {livePrice !== null && (
            <span
              className={`font-mono text-[15px] font-semibold transition-colors ${
                priceChange === "up"
                  ? "text-profit"
                  : priceChange === "down"
                    ? "text-loss"
                    : "text-text-primary"
              }`}
            >
              {formatUSD(livePrice)}
            </span>
          )}
        </div>
        <div className="flex gap-0.5 bg-bg-secondary rounded-[var(--radius-sm)] p-0.5">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => handleTimeframeChange(tf)}
              className={`px-2.5 py-1 text-[11px] font-mono font-medium rounded-[6px] transition-all ${
                activeTimeframe === tf
                  ? "bg-bg-primary text-text-primary shadow-sm"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>
      <div ref={chartContainerRef} className="flex-1 min-h-0" />
    </div>
  );
}
