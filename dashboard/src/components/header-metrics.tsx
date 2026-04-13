"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Sun, Moon, Activity, Wallet, TrendingDown, Hash } from "lucide-react";
import { useTheme } from "@/lib/theme";
import { API_URL, formatUSD, formatPct } from "@/lib/utils";
import type { Portfolio } from "@/lib/types";

export function HeaderMetrics() {
  const { theme, toggle } = useTheme();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [cycle, setCycle] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [pRes, hRes] = await Promise.all([
          fetch(`${API_URL}/api/portfolio`),
          fetch(`${API_URL}/api/health`),
        ]);
        if (pRes.ok) setPortfolio(await pRes.json());
        if (hRes.ok) setCycle((await hRes.json()).cycle);
      } catch {
        /* backend offline */
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-border">
      <div className="flex items-center gap-3">
        <h1 className="text-[15px] font-semibold tracking-tight text-text-primary">
          TradeBot
        </h1>
        <div className="flex items-center gap-1.5">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-profit opacity-60" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-profit" />
          </span>
          <span className="text-[11px] text-text-tertiary font-medium">
            Paper Trading
          </span>
        </div>
      </div>

      <div className="flex items-center gap-8">
        <Metric
          icon={<Wallet size={13} />}
          label="Portfolio"
          value={portfolio ? formatUSD(portfolio.value) : "--"}
        />
        <Metric
          icon={<TrendingDown size={13} />}
          label="Drawdown"
          value={portfolio ? formatPct(-portfolio.drawdown_pct) : "--"}
          negative={portfolio ? portfolio.drawdown_pct > 2 : false}
        />
        <Metric
          icon={<Hash size={13} />}
          label="Cycle"
          value={String(cycle)}
        />

        <button
          onClick={toggle}
          className="p-2 rounded-[var(--radius-sm)] hover:bg-bg-tertiary text-text-secondary"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </header>
  );
}

function Metric({
  icon,
  label,
  value,
  negative = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  negative?: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="text-text-tertiary">{icon}</span>
      <div className="flex flex-col">
        <span className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">
          {label}
        </span>
        <motion.span
          className={`font-mono text-[13px] font-medium ${
            negative ? "text-loss" : "text-text-primary"
          }`}
          key={value}
          initial={{ opacity: 0.6 }}
          animate={{ opacity: 1 }}
        >
          {value}
        </motion.span>
      </div>
    </div>
  );
}
