"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { API_URL, formatUSD, formatPct } from "@/lib/utils";
import type { Position } from "@/lib/types";

export function PositionsTable() {
  const [positions, setPositions] = useState<Position[]>([]);

  useEffect(() => {
    const fetchPositions = async () => {
      try {
        const res = await fetch(`${API_URL}/api/positions`);
        if (res.ok) setPositions(await res.json());
      } catch {
        // backend not connected
      }
    };
    fetchPositions();
    const interval = setInterval(fetchPositions, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-card-border">
        <h2 className="text-sm font-semibold tracking-wide">POSITIONS</h2>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted border-b border-card-border">
              <th className="text-left px-4 py-2 font-medium">Symbol</th>
              <th className="text-left px-2 py-2 font-medium">Side</th>
              <th className="text-right px-2 py-2 font-medium">Qty</th>
              <th className="text-right px-2 py-2 font-medium">Entry</th>
              <th className="text-right px-2 py-2 font-medium">Current</th>
              <th className="text-right px-4 py-2 font-medium">P&L</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-8 text-muted">
                  No open positions
                </td>
              </tr>
            )}
            {positions.map((pos) => (
              <motion.tr
                key={pos.symbol}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="border-b border-card-border/30 hover:bg-card-border/20"
              >
                <td className="px-4 py-2 font-mono font-semibold">
                  {pos.symbol}
                </td>
                <td className="px-2 py-2">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      pos.side === "long"
                        ? "bg-profit/20 text-profit"
                        : "bg-loss/20 text-loss"
                    }`}
                  >
                    {pos.side.toUpperCase()}
                  </span>
                </td>
                <td className="px-2 py-2 text-right font-mono">
                  {pos.quantity.toFixed(6)}
                </td>
                <td className="px-2 py-2 text-right font-mono">
                  {formatUSD(pos.entry_price)}
                </td>
                <td className="px-2 py-2 text-right font-mono">
                  {formatUSD(pos.current_price)}
                </td>
                <td
                  className={`px-4 py-2 text-right font-mono font-semibold ${
                    pos.unrealized_pnl >= 0 ? "text-profit" : "text-loss"
                  }`}
                >
                  {formatUSD(pos.unrealized_pnl)}{" "}
                  <span className="text-[10px]">
                    ({formatPct(pos.unrealized_pnl_pct)})
                  </span>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
