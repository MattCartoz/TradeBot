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
        /* offline */
      }
    };
    fetchPositions();
    const interval = setInterval(fetchPositions, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3">
        <h2 className="text-[13px] font-semibold text-text-primary">
          Positions
        </h2>
      </div>

      <div className="flex-1 overflow-auto px-5">
        {positions.length === 0 ? (
          <div className="flex items-center justify-center h-32">
            <p className="text-[13px] text-text-tertiary">No open positions</p>
          </div>
        ) : (
          <div className="space-y-2">
            {positions.map((pos) => (
              <motion.div
                key={pos.symbol}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center justify-between py-2.5 border-b border-border last:border-0"
              >
                <div className="flex items-center gap-3">
                  <div>
                    <span className="text-[13px] font-mono font-semibold text-text-primary">
                      {pos.symbol}
                    </span>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span
                        className={`text-[10px] font-medium uppercase ${
                          pos.side === "long" ? "text-profit" : "text-loss"
                        }`}
                      >
                        {pos.side}
                      </span>
                      <span className="text-[11px] font-mono text-text-tertiary">
                        {pos.quantity.toFixed(6)}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <span
                    className={`text-[13px] font-mono font-semibold ${
                      pos.unrealized_pnl >= 0 ? "text-profit" : "text-loss"
                    }`}
                  >
                    {formatUSD(pos.unrealized_pnl)}
                  </span>
                  <div className="text-[11px] font-mono text-text-tertiary mt-0.5">
                    {formatPct(pos.unrealized_pnl_pct)}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
