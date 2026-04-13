"use client";

import { useEffect, useState } from "react";
import { ChevronRight } from "lucide-react";
import { API_URL, formatUSD, formatPct } from "@/lib/utils";
import type { Trade } from "@/lib/types";

export function TradeHistory() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    const fetchTrades = async () => {
      try {
        const res = await fetch(`${API_URL}/api/trades`);
        if (res.ok) setTrades(await res.json());
      } catch {
        /* offline */
      }
    };
    fetchTrades();
    const interval = setInterval(fetchTrades, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3">
        <h2 className="text-[13px] font-semibold text-text-primary">
          Trade History
        </h2>
      </div>

      <div className="flex-1 overflow-auto px-5">
        {trades.length === 0 ? (
          <div className="flex items-center justify-center h-32">
            <p className="text-[13px] text-text-tertiary">
              No trades yet
            </p>
          </div>
        ) : (
          <div className="space-y-px">
            {trades.map((trade) => {
              const expanded = expandedId === trade.id;
              return (
                <div key={trade.id}>
                  <button
                    onClick={() => setExpandedId(expanded ? null : trade.id)}
                    className="w-full flex items-center justify-between py-2.5 border-b border-border text-left group"
                  >
                    <div className="flex items-center gap-3">
                      <ChevronRight
                        size={12}
                        className={`text-text-tertiary transition-transform ${
                          expanded ? "rotate-90" : ""
                        }`}
                      />
                      <div>
                        <span className="text-[13px] font-mono font-semibold text-text-primary">
                          {trade.symbol}
                        </span>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span
                            className={`text-[10px] font-medium uppercase ${
                              trade.side === "buy" ? "text-profit" : "text-loss"
                            }`}
                          >
                            {trade.side}
                          </span>
                          <span className="text-[11px] text-text-tertiary">
                            {formatUSD(trade.entry_price)}
                          </span>
                          {trade.exit_price && (
                            <>
                              <span className="text-[11px] text-text-tertiary">
                                &rarr;
                              </span>
                              <span className="text-[11px] text-text-tertiary">
                                {formatUSD(trade.exit_price)}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      {trade.pnl !== null ? (
                        <span
                          className={`text-[13px] font-mono font-semibold ${
                            trade.pnl >= 0 ? "text-profit" : "text-loss"
                          }`}
                        >
                          {formatUSD(trade.pnl)}
                        </span>
                      ) : (
                        <span className="text-[11px] font-medium text-accent">
                          Open
                        </span>
                      )}
                    </div>
                  </button>

                  {expanded && trade.post_mortem && (
                    <div className="pl-8 pr-4 py-3 bg-bg-secondary rounded-[var(--radius-sm)] mb-2 mt-1">
                      <p className="text-[11px] text-text-secondary leading-relaxed">
                        {JSON.stringify(trade.post_mortem, null, 2)}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
