"use client";

import { useEffect, useState } from "react";
import { Play, Square, RotateCw } from "lucide-react";
import { API_URL } from "@/lib/utils";
import type { Portfolio } from "@/lib/types";

function ProgressBar({
  label,
  value,
  max,
  variant = "default",
}: {
  label: string;
  value: number;
  max: number;
  variant?: "default" | "danger";
}) {
  const pct = Math.min((value / max) * 100, 100);
  const isDanger = variant === "danger" || pct > 70;

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between">
        <span className="text-[11px] text-text-secondary">{label}</span>
        <span className="text-[11px] font-mono text-text-primary">
          {value.toFixed(1)}%
          <span className="text-text-tertiary"> / {max}%</span>
        </span>
      </div>
      <div className="h-1 bg-bg-tertiary rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-out ${
            isDanger ? "bg-loss" : "bg-accent"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function RiskDashboard() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [loopRunning, setLoopRunning] = useState(false);

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
        /* offline */
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const risk = (config?.risk as Record<string, number>) || {};
  const patience = (config?.patience as Record<string, number>) || {};

  const runCycle = async () => {
    await fetch(`${API_URL}/api/run-cycle`, { method: "POST" });
  };

  const toggleLoop = async () => {
    if (loopRunning) {
      await fetch(`${API_URL}/api/stop`, { method: "POST" });
    } else {
      await fetch(`${API_URL}/api/start`, { method: "POST" });
    }
    setLoopRunning(!loopRunning);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3">
        <h2 className="text-[13px] font-semibold text-text-primary">
          Risk & Controls
        </h2>
      </div>

      <div className="flex-1 px-5 space-y-5 overflow-auto pb-4">
        <ProgressBar
          label="Drawdown"
          value={portfolio?.drawdown_pct || 0}
          max={risk.max_drawdown_pct || 10}
          variant={
            (portfolio?.drawdown_pct || 0) > (risk.max_drawdown_pct || 10) * 0.7
              ? "danger"
              : "default"
          }
        />

        <ProgressBar
          label="Portfolio Risk"
          value={portfolio?.risk_pct || 0}
          max={risk.max_portfolio_risk_pct || 15}
        />

        <div className="space-y-2.5 pt-1">
          <Row label="Max Position" value={`${risk.max_position_size_pct || 5}%`} />
          <Row label="Conviction" value={String(patience.conviction_threshold || 0.7)} />
          <Row label="Max Trades / Day" value={String(patience.max_trades_per_day || 3)} />
          <Row label="Cooldown" value={`${patience.cooldown_minutes || 60}m`} />
        </div>

        <div className="pt-2 flex gap-2">
          <button
            onClick={runCycle}
            className="flex-1 flex items-center justify-center gap-1.5 h-8 rounded-[var(--radius-sm)] text-[12px] font-medium bg-bg-tertiary text-text-primary hover:bg-border-strong transition-colors"
          >
            <RotateCw size={12} />
            Run Cycle
          </button>
          <button
            onClick={toggleLoop}
            className={`flex-1 flex items-center justify-center gap-1.5 h-8 rounded-[var(--radius-sm)] text-[12px] font-medium transition-colors ${
              loopRunning
                ? "bg-loss/10 text-loss hover:bg-loss/20"
                : "bg-profit/10 text-profit hover:bg-profit/20"
            }`}
          >
            {loopRunning ? (
              <>
                <Square size={10} />
                Stop
              </>
            ) : (
              <>
                <Play size={10} />
                Start
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-[11px] text-text-secondary">{label}</span>
      <span className="text-[11px] font-mono text-text-primary">{value}</span>
    </div>
  );
}
