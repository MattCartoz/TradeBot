"use client";

import { HeaderMetrics } from "@/components/header-metrics";
import { LiveChart } from "@/components/live-chart";
import { AgentDesk } from "@/components/agent-desk";
import { PositionsTable } from "@/components/positions-table";
import { TradeHistory } from "@/components/trade-history";
import { RiskDashboard } from "@/components/risk-dashboard";

export default function TradingFloor() {
  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Top bar — portfolio metrics */}
      <HeaderMetrics />

      {/* Main grid — 6-panel trading floor layout */}
      <div className="flex-1 grid grid-cols-[1fr_360px] grid-rows-[1fr_1fr] gap-px bg-card-border overflow-hidden">
        {/* Panel 1: Live Chart (top left) */}
        <div className="bg-card">
          <LiveChart />
        </div>

        {/* Panel 2: Agent Desk (top right — spans full height) */}
        <div className="bg-card row-span-2">
          <AgentDesk />
        </div>

        {/* Panel 3+4+5: Bottom left — Positions, Trade History, Risk */}
        <div className="bg-card grid grid-cols-3 gap-px">
          <div className="bg-card col-span-1">
            <PositionsTable />
          </div>
          <div className="bg-card col-span-1">
            <TradeHistory />
          </div>
          <div className="bg-card col-span-1">
            <RiskDashboard />
          </div>
        </div>
      </div>
    </div>
  );
}
