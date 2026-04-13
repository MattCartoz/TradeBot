"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  type IChartApi,
  type ISeriesApi,
  ColorType,
  type CandlestickData,
  type Time,
} from "lightweight-charts";
import { useTheme } from "@/lib/theme";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1D"];

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
  },
};

export function LiveChart() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [activeTimeframe, setActiveTimeframe] = useState("1h");
  const [activeSymbol, setActiveSymbol] = useState("BTC/USD");
  const { theme } = useTheme();

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

    const series = chart.addSeries(CandlestickSeries, {
      upColor: t.up,
      downColor: t.down,
      borderUpColor: t.up,
      borderDownColor: t.down,
      wickUpColor: t.up,
      wickDownColor: t.down,
    });

    // Sample data for display
    const now = Math.floor(Date.now() / 1000);
    const data: CandlestickData<Time>[] = [];
    let price = 67000;
    for (let i = 100; i >= 0; i--) {
      const time = (now - i * 3600) as Time;
      const open = price;
      const change = (Math.random() - 0.48) * 500;
      const close = open + change;
      const high = Math.max(open, close) + Math.random() * 300;
      const low = Math.min(open, close) - Math.random() * 300;
      data.push({ time, open, high, low, close });
      price = close;
    }
    series.setData(data);
    chart.timeScale().fitContent();

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
      ro.disconnect();
      chart.remove();
    };
  }, [theme]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3">
        <div className="flex items-center gap-4">
          <select
            value={activeSymbol}
            onChange={(e) => setActiveSymbol(e.target.value)}
            className="bg-transparent text-[13px] font-semibold text-text-primary font-mono appearance-none cursor-pointer pr-4"
          >
            <option value="BTC/USD">BTC / USD</option>
            <option value="ETH/USD">ETH / USD</option>
          </select>
        </div>
        <div className="flex gap-0.5 bg-bg-secondary rounded-[var(--radius-sm)] p-0.5">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setActiveTimeframe(tf)}
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
