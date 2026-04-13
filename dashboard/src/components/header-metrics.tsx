"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { API_URL, formatUSD, formatPct } from "@/lib/utils";
import type { Portfolio } from "@/lib/types";

export function HeaderMetrics() {
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
        if (hRes.ok) {
          const h = await hRes.json();
          setCycle(h.cycle);
        }
      } catch {
        // backend not connected yet
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="border-b border-card-border bg-card px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold tracking-tight text-cyan">
            TRADEBOT
          </h1>
          <span className="text-xs text-muted font-mono">
            Multi-Agent Trading Floor
          </span>
        </div>

        <div className="flex items-center gap-8">
          <Metric
            label="Portfolio"
            value={portfolio ? formatUSD(portfolio.value) : "—"}
          />
          <Metric
            label="Cash"
            value={portfolio ? formatUSD(portfolio.cash) : "—"}
          />
          <Metric
            label="Drawdown"
            value={portfolio ? formatPct(-portfolio.drawdown_pct) : "—"}
            negative={portfolio ? portfolio.drawdown_pct > 0 : false}
          />
          <Metric label="Cycle" value={`#${cycle}`} />
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-profit opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-profit" />
            </span>
            <span className="text-xs text-muted">Paper</span>
          </div>
        </div>
      </div>
    </header>
  );
}

function Metric({
  label,
  value,
  negative = false,
}: {
  label: string;
  value: string;
  negative?: boolean;
}) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-muted">
        {label}
      </span>
      <motion.span
        className={`font-mono text-sm font-semibold ${
          negative ? "text-loss" : "text-foreground"
        }`}
        key={value}
        initial={{ opacity: 0.5 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        {value}
      </motion.span>
    </div>
  );
}
