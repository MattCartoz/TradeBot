"use client";

import { useEffect, useState } from "react";
import { TrendingUp } from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { API_URL, formatUSD } from "@/lib/utils";
import { useTheme } from "@/lib/theme";

interface EquityPoint {
  timestamp: string;
  cumulative_pnl: number;
}

function formatAxisDate(ts: string): string {
  const d = new Date(ts);
  return `${(d.getMonth() + 1).toString().padStart(2, "0")}/${d
    .getDate()
    .toString()
    .padStart(2, "0")}`;
}

function formatTooltipDate(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number; payload: EquityPoint }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0];
  return (
    <div className="glass-card px-3 py-2 space-y-0.5">
      <p className="text-[10px] text-text-tertiary">
        {formatTooltipDate(point.payload.timestamp)}
      </p>
      <p
        className={`text-[13px] font-mono font-semibold ${
          point.value >= 0 ? "text-profit" : "text-loss"
        }`}
      >
        {formatUSD(point.value)}
      </p>
    </div>
  );
}

export function EquityCurve() {
  const { theme } = useTheme();
  const [data, setData] = useState<EquityPoint[]>([]);

  useEffect(() => {
    const fetchEquity = async () => {
      try {
        const res = await fetch(`${API_URL}/api/equity-curve`);
        if (res.ok) {
          const raw: EquityPoint[] = await res.json();
          setData(raw);
        }
      } catch {
        /* backend offline */
      }
    };
    fetchEquity();
    const interval = setInterval(fetchEquity, 30000);
    return () => clearInterval(interval);
  }, []);

  const lastValue = data.length > 0 ? data[data.length - 1].cumulative_pnl : 0;
  const isPositive = lastValue >= 0;

  const gridColor =
    theme === "dark" ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.04)";
  const axisColor =
    theme === "dark" ? "rgba(255,255,255,0.3)" : "rgba(0,0,0,0.3)";

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3 flex items-center justify-between">
        <h2 className="text-[13px] font-semibold text-text-primary">
          Equity Curve
        </h2>
        {data.length > 0 && (
          <span
            className={`font-mono text-[13px] font-semibold ${
              isPositive ? "text-profit" : "text-loss"
            }`}
          >
            {formatUSD(lastValue)}
          </span>
        )}
      </div>

      <div className="flex-1 px-3 pb-3 min-h-[200px]">
        {data.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2">
            <TrendingUp size={20} className="text-text-tertiary" />
            <p className="text-[13px] text-text-tertiary">
              No closed trades yet
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 4, right: 8, bottom: 0, left: 8 }}
            >
              <defs>
                <linearGradient id="equityGradientPos" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor="var(--profit)"
                    stopOpacity={0.24}
                  />
                  <stop
                    offset="100%"
                    stopColor="var(--profit)"
                    stopOpacity={0}
                  />
                </linearGradient>
                <linearGradient id="equityGradientNeg" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor="var(--loss)"
                    stopOpacity={0.24}
                  />
                  <stop
                    offset="100%"
                    stopColor="var(--loss)"
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid
                stroke={gridColor}
                strokeDasharray="3 3"
                vertical={false}
              />
              <XAxis
                dataKey="timestamp"
                tickFormatter={formatAxisDate}
                tick={{
                  fontSize: 10,
                  fontFamily: "var(--font-mono)",
                  fill: axisColor,
                }}
                axisLine={false}
                tickLine={false}
                minTickGap={40}
              />
              <YAxis
                tickFormatter={(v: number) => formatUSD(v)}
                tick={{
                  fontSize: 10,
                  fontFamily: "var(--font-mono)",
                  fill: axisColor,
                }}
                axisLine={false}
                tickLine={false}
                width={72}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{
                  stroke: axisColor,
                  strokeDasharray: "3 3",
                }}
              />
              <Area
                type="monotone"
                dataKey="cumulative_pnl"
                stroke={isPositive ? "var(--profit)" : "var(--loss)"}
                strokeWidth={1.5}
                fill={
                  isPositive
                    ? "url(#equityGradientPos)"
                    : "url(#equityGradientNeg)"
                }
                animationDuration={800}
                animationEasing="ease-out"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
