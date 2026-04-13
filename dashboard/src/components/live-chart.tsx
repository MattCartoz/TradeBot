"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  ColorType,
  type CandlestickData,
  type Time,
} from "lightweight-charts";
import { WS_URL } from "@/lib/utils";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1D"];

export function LiveChart() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [activeTimeframe, setActiveTimeframe] = useState("1h");
  const [activeSymbol, setActiveSymbol] = useState("BTC/USD");

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0d1117" },
        textColor: "#8b949e",
        fontFamily: "var(--font-geist-mono), monospace",
      },
      grid: {
        vertLines: { color: "#1e2430" },
        horzLines: { color: "#1e2430" },
      },
      crosshair: {
        vertLine: { color: "#30363d", labelBackgroundColor: "#161b22" },
        horzLine: { color: "#30363d", labelBackgroundColor: "#161b22" },
      },
      rightPriceScale: {
        borderColor: "#30363d",
      },
      timeScale: {
        borderColor: "#30363d",
        timeVisible: true,
      },
    });

    chartRef.current = chart;

    const series = chart.addCandlestickSeries({
      upColor: "#00c853",
      downColor: "#ff1744",
      borderUpColor: "#00c853",
      borderDownColor: "#ff1744",
      wickUpColor: "#00c853",
      wickDownColor: "#ff1744",
    });
    seriesRef.current = series;

    // Generate sample data for display
    const now = Math.floor(Date.now() / 1000);
    const sampleData: CandlestickData<Time>[] = [];
    let price = 67000;
    for (let i = 100; i >= 0; i--) {
      const time = (now - i * 3600) as Time;
      const open = price;
      const change = (Math.random() - 0.48) * 500;
      const close = open + change;
      const high = Math.max(open, close) + Math.random() * 300;
      const low = Math.min(open, close) - Math.random() * 300;
      sampleData.push({ time, open, high, low, close });
      price = close;
    }
    series.setData(sampleData);
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Chart header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-card-border">
        <div className="flex items-center gap-4">
          <select
            value={activeSymbol}
            onChange={(e) => setActiveSymbol(e.target.value)}
            className="bg-background border border-card-border rounded px-2 py-1 text-sm font-mono text-foreground"
          >
            <option value="BTC/USD">BTC/USD</option>
            <option value="ETH/USD">ETH/USD</option>
          </select>
          <span className="font-mono text-lg font-bold text-profit">
            $67,418.00
          </span>
        </div>
        <div className="flex gap-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setActiveTimeframe(tf)}
              className={`px-2 py-1 text-xs font-mono rounded transition-colors ${
                activeTimeframe === tf
                  ? "bg-cyan/20 text-cyan"
                  : "text-muted hover:text-foreground hover:bg-card-border/50"
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart area */}
      <div ref={chartContainerRef} className="flex-1 min-h-0" />
    </div>
  );
}
