"use client";

import { HeaderMetrics } from "@/components/header-metrics";
import { LiveChart } from "@/components/live-chart";
import { AgentDesk } from "@/components/agent-desk";
import { PositionsTable } from "@/components/positions-table";
import { TradeHistory } from "@/components/trade-history";
import { RiskDashboard } from "@/components/risk-dashboard";

export default function TradingFloor() {
  return (
    <div className="flex flex-col h-screen bg-bg-secondary">
      <HeaderMetrics />

      <div className="flex-1 p-3 overflow-hidden">
        <div className="h-full grid grid-cols-[1fr_340px] grid-rows-[1.2fr_1fr] gap-3">
          {/* Chart */}
          <div className="glass-card overflow-hidden">
            <LiveChart />
          </div>

          {/* Agent Activity */}
          <div className="glass-card overflow-hidden row-span-2">
            <AgentDesk />
          </div>

          {/* Bottom row */}
          <div className="grid grid-cols-3 gap-3 min-h-0">
            <div className="glass-card overflow-hidden">
              <PositionsTable />
            </div>
            <div className="glass-card overflow-hidden">
              <TradeHistory />
            </div>
            <div className="glass-card overflow-hidden">
              <RiskDashboard />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
