"use client";

import { useState } from "react";
import { BarChart3, Activity, LayoutDashboard } from "lucide-react";
import { HeaderMetrics } from "@/components/header-metrics";
import { LiveChart } from "@/components/live-chart";
import { AgentDesk } from "@/components/agent-desk";
import { PositionsTable } from "@/components/positions-table";
import { TradeHistory } from "@/components/trade-history";
import { RiskDashboard } from "@/components/risk-dashboard";
import { StatsOverview } from "@/components/stats-overview";
import { EquityCurve } from "@/components/equity-curve";
import { CycleActivity } from "@/components/cycle-activity";
import { SystemHealth } from "@/components/system-health";

type View = "cockpit" | "trading" | "activity";

const VIEWS: { id: View; label: string; icon: React.ReactNode }[] = [
  { id: "cockpit", label: "Cockpit", icon: <LayoutDashboard size={14} /> },
  { id: "trading", label: "Trading", icon: <BarChart3 size={14} /> },
  { id: "activity", label: "Activity", icon: <Activity size={14} /> },
];

export default function TradingFloor() {
  const [view, setView] = useState<View>("cockpit");

  return (
    <div className="flex flex-col h-screen bg-bg-secondary">
      <HeaderMetrics />

      {/* View Switcher */}
      <div className="px-4 pt-3 pb-0">
        <div className="flex gap-0.5 bg-bg-tertiary/50 rounded-[var(--radius-sm)] p-0.5 w-fit">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              onClick={() => setView(v.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium rounded-[6px] transition-all ${
                view === v.id
                  ? "bg-bg-primary text-text-primary shadow-sm"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
            >
              {v.icon}
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {/* Cockpit View — the pilot's overview */}
      {view === "cockpit" && (
        <div className="flex-1 p-3 overflow-auto">
          <div className="space-y-3">
            {/* Stats row */}
            <StatsOverview />

            {/* Main content: Equity + Positions | System + Risk */}
            <div className="grid grid-cols-[1fr_380px] gap-3">
              {/* Left column */}
              <div className="space-y-3">
                <div className="glass-card overflow-hidden" style={{ height: 320 }}>
                  <EquityCurve />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="glass-card overflow-hidden" style={{ height: 340 }}>
                    <PositionsTable />
                  </div>
                  <div className="glass-card overflow-hidden" style={{ height: 340 }}>
                    <TradeHistory />
                  </div>
                </div>
              </div>

              {/* Right column */}
              <div className="space-y-3">
                <div className="glass-card overflow-hidden" style={{ height: 320 }}>
                  <SystemHealth />
                </div>
                <div className="glass-card overflow-hidden" style={{ height: 340 }}>
                  <RiskDashboard />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Trading View — chart focused */}
      {view === "trading" && (
        <div className="flex-1 p-3 overflow-hidden">
          <div className="h-full grid grid-cols-[1fr_340px] grid-rows-[1.2fr_1fr] gap-3">
            <div className="glass-card overflow-hidden">
              <LiveChart />
            </div>
            <div className="glass-card overflow-hidden row-span-2">
              <AgentDesk />
            </div>
            <div className="grid grid-cols-2 gap-3 min-h-0">
              <div className="glass-card overflow-hidden">
                <PositionsTable />
              </div>
              <div className="glass-card overflow-hidden">
                <RiskDashboard />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Activity View — agent feed + cycle history */}
      {view === "activity" && (
        <div className="flex-1 p-3 overflow-hidden">
          <div className="h-full grid grid-cols-[1fr_1fr] gap-3">
            <div className="glass-card overflow-hidden">
              <AgentDesk />
            </div>
            <div className="glass-card overflow-hidden">
              <CycleActivity />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
