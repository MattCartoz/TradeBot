"use client";

import { useEffect, useState } from "react";
import {
  TrendingUp,
  Target,
  BarChart3,
  Hash,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
} from "lucide-react";
import { API_URL, formatUSD, formatPct } from "@/lib/utils";

interface Stats {
  total_pnl: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  avg_win: number;
  avg_loss: number;
}

function StatCard({
  icon,
  label,
  value,
  sub,
  color = "text-text-primary",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="flex-1 min-w-[140px] rounded-[var(--radius-md)] bg-bg-secondary/60 border border-border px-4 py-3.5 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-text-tertiary">{icon}</span>
        <span className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">
          {label}
        </span>
      </div>
      <div>
        <span className={`font-mono text-[20px] font-semibold tracking-tight ${color}`}>
          {value}
        </span>
        {sub && (
          <span className="block text-[10px] font-mono text-text-tertiary mt-0.5">
            {sub}
          </span>
        )}
      </div>
    </div>
  );
}

export function StatsOverview() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(`${API_URL}/api/stats`);
        if (res.ok) setStats(await res.json());
      } catch {
        /* backend offline */
      }
    };
    fetchStats();
    const interval = setInterval(fetchStats, 15000);
    return () => clearInterval(interval);
  }, []);

  const pnlColor =
    stats && stats.total_pnl >= 0 ? "text-profit" : stats ? "text-loss" : "text-text-primary";

  return (
    <div className="w-full">
      <div className="px-1 pb-3">
        <h2 className="text-[13px] font-semibold text-text-primary">
          Performance Overview
        </h2>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-1">
        <StatCard
          icon={<TrendingUp size={13} />}
          label="Total P&L"
          value={stats ? formatUSD(stats.total_pnl) : "--"}
          color={pnlColor}
        />
        <StatCard
          icon={<Target size={13} />}
          label="Win Rate"
          value={stats ? `${stats.win_rate.toFixed(1)}%` : "--"}
          color="text-text-primary"
        />
        <StatCard
          icon={<BarChart3 size={13} />}
          label="Profit Factor"
          value={stats ? stats.profit_factor.toFixed(2) : "--"}
          color="text-text-primary"
        />
        <StatCard
          icon={<Hash size={13} />}
          label="Total Trades"
          value={stats ? String(stats.total_trades) : "--"}
          color="text-text-primary"
        />
        <StatCard
          icon={<ArrowUpRight size={13} />}
          label="Avg Win / Loss"
          value={stats ? formatUSD(stats.avg_win) : "--"}
          sub={stats ? `Loss ${formatUSD(stats.avg_loss)}` : undefined}
          color="text-profit"
        />
        <StatCard
          icon={<Activity size={13} />}
          label="Sharpe Ratio"
          value="--"
          sub="Coming soon"
          color="text-text-primary"
        />
      </div>
    </div>
  );
}
