"use client";

import { useEffect, useState } from "react";
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
        // backend not connected
      }
    };
    fetchTrades();
    const interval = setInterval(fetchTrades, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-card-border">
        <h2 className="text-sm font-semibold tracking-wide">TRADE HISTORY</h2>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted border-b border-card-border">
              <th className="text-left px-4 py-2 font-medium">Symbol</th>
              <th className="text-left px-2 py-2 font-medium">Side</th>
              <th className="text-right px-2 py-2 font-medium">Entry</th>
              <th className="text-right px-2 py-2 font-medium">Exit</th>
              <th className="text-right px-2 py-2 font-medium">P&L</th>
              <th className="text-right px-4 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-8 text-muted">
                  No trades yet — the desk is patient
                </td>
              </tr>
            )}
            {trades.map((trade) => (
              <tr
                key={trade.id}
                className="border-b border-card-border/30 hover:bg-card-border/20 cursor-pointer"
                onClick={() =>
                  setExpandedId(expandedId === trade.id ? null : trade.id)
                }
              >
                <td className="px-4 py-2 font-mono font-semibold">
                  {trade.symbol}
                </td>
                <td className="px-2 py-2">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      trade.side === "buy"
                        ? "bg-profit/20 text-profit"
                        : "bg-loss/20 text-loss"
                    }`}
                  >
                    {trade.side.toUpperCase()}
                  </span>
                </td>
                <td className="px-2 py-2 text-right font-mono">
                  {formatUSD(trade.entry_price)}
                </td>
                <td className="px-2 py-2 text-right font-mono">
                  {trade.exit_price ? formatUSD(trade.exit_price) : "—"}
                </td>
                <td
                  className={`px-2 py-2 text-right font-mono font-semibold ${
                    trade.pnl !== null
                      ? trade.pnl >= 0
                        ? "text-profit"
                        : "text-loss"
                      : "text-muted"
                  }`}
                >
                  {trade.pnl !== null ? formatUSD(trade.pnl) : "Open"}
                </td>
                <td className="px-4 py-2 text-right">
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded ${
                      trade.status === "open"
                        ? "bg-cyan/20 text-cyan"
                        : trade.pnl !== null && trade.pnl >= 0
                          ? "bg-profit/20 text-profit"
                          : "bg-loss/20 text-loss"
                    }`}
                  >
                    {trade.status.toUpperCase()}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
