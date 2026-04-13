"use client";

import { useEffect, useState } from "react";
import { API_URL, formatPct } from "@/lib/utils";
import type { Portfolio } from "@/lib/types";

function Gauge({
  label,
  value,
  max,
  color,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
}) {
  const pct = Math.min((value / max) * 100, 100);

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px]">
        <span className="text-muted">{label}</span>
        <span className="font-mono text-foreground">
          {value.toFixed(1)}% / {max}%
        </span>
      </div>
      <div className="h-1.5 bg-card-border rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function RiskDashboard() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [pRes, cRes] = await Promise.all([
          fetch(`${API_URL}/api/portfolio`),
          fetch(`${API_URL}/api/config`),
        ]);
        if (pRes.ok) setPortfolio(await pRes.json());
        if (cRes.ok) setConfig(await cRes.json());
      } catch {
        // backend not connected
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const risk = (config?.risk as Record<string, number>) || {};
  const patience = (config?.patience as Record<string, number>) || {};

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-card-border">
        <h2 className="text-sm font-semibold tracking-wide">RISK</h2>
      </div>

      <div className="flex-1 px-4 py-3 space-y-4 overflow-auto">
        <Gauge
          label="Portfolio Drawdown"
          value={portfolio?.drawdown_pct || 0}
          max={risk.max_drawdown_pct || 10}
          color={
            (portfolio?.drawdown_pct || 0) > (risk.max_drawdown_pct || 10) * 0.7
              ? "bg-loss"
              : "bg-profit"
          }
        />

        <Gauge
          label="Portfolio Risk"
          value={0}
          max={risk.max_portfolio_risk_pct || 15}
          color="bg-cyan"
        />

        <div className="pt-2 space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-muted">Max Position Size</span>
            <span className="font-mono">{risk.max_position_size_pct || 5}%</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted">Conviction Threshold</span>
            <span className="font-mono">{patience.conviction_threshold || 0.7}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted">Max Trades/Day</span>
            <span className="font-mono">{patience.max_trades_per_day || 3}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted">Cooldown</span>
            <span className="font-mono">{patience.cooldown_minutes || 60}m</span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="pt-3 space-y-2">
          <button
            onClick={() => fetch(`${API_URL}/api/run-cycle`, { method: "POST" })}
            className="w-full py-2 rounded text-xs font-semibold bg-cyan/20 text-cyan hover:bg-cyan/30 transition-colors"
          >
            Run Single Cycle
          </button>
          <button
            onClick={() => fetch(`${API_URL}/api/start`, { method: "POST" })}
            className="w-full py-2 rounded text-xs font-semibold bg-profit/20 text-profit hover:bg-profit/30 transition-colors"
          >
            Start Auto Loop
          </button>
          <button
            onClick={() => fetch(`${API_URL}/api/stop`, { method: "POST" })}
            className="w-full py-2 rounded text-xs font-semibold bg-loss/20 text-loss hover:bg-loss/30 transition-colors"
          >
            Stop Loop
          </button>
        </div>
      </div>
    </div>
  );
}
