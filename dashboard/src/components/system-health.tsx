"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Server,
  Radio,
  Layers,
} from "lucide-react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from "recharts";
import { API_URL } from "@/lib/utils";
import { useTheme } from "@/lib/theme";

interface HealthData {
  status: string;
  cycle: number;
  uptime?: number;
}

interface CycleStats {
  total_cycles: number;
  trades: number;
  holds: number;
  vetoes: number;
  errors: number;
  current_regime: string;
}

type ConnectionStatus = "connected" | "disconnected" | "checking";

function StatusDot({ status }: { status: ConnectionStatus }) {
  if (status === "connected") {
    return (
      <span className="relative flex h-1.5 w-1.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-profit opacity-60" />
        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-profit" />
      </span>
    );
  }
  if (status === "checking") {
    return <Loader2 size={10} className="text-warning animate-spin" />;
  }
  return <span className="inline-flex rounded-full h-1.5 w-1.5 bg-loss" />;
}

function ConnectionRow({
  label,
  status,
}: {
  label: string;
  status: ConnectionStatus;
}) {
  const statusLabel =
    status === "connected"
      ? "Online"
      : status === "checking"
        ? "Checking"
        : "Offline";
  const statusColor =
    status === "connected"
      ? "text-profit"
      : status === "checking"
        ? "text-warning"
        : "text-loss";

  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-[11px] text-text-secondary">{label}</span>
      <div className="flex items-center gap-1.5">
        <StatusDot status={status} />
        <span className={`text-[11px] font-medium ${statusColor}`}>
          {statusLabel}
        </span>
      </div>
    </div>
  );
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number }>;
}

function DonutTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="glass-card px-3 py-1.5">
      <span className="text-[11px] text-text-primary">
        {item.name}:{" "}
        <span className="font-mono font-semibold">{item.value}</span>
      </span>
    </div>
  );
}

const DONUT_COLORS = [
  "var(--profit)",
  "var(--accent)",
  "var(--warning)",
  "var(--loss)",
];

export function SystemHealth() {
  const { theme } = useTheme();
  const [health, setHealth] = useState<HealthData | null>(null);
  const [cycleStats, setCycleStats] = useState<CycleStats | null>(null);
  const [apiStatus, setApiStatus] = useState<ConnectionStatus>("checking");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [hRes, cRes] = await Promise.all([
          fetch(`${API_URL}/api/health`),
          fetch(`${API_URL}/api/cycle-stats`),
        ]);
        if (hRes.ok) {
          setHealth(await hRes.json());
          setApiStatus("connected");
        } else {
          setApiStatus("disconnected");
        }
        if (cRes.ok) setCycleStats(await cRes.json());
      } catch {
        setApiStatus("disconnected");
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const donutData = cycleStats
    ? [
        { name: "Trades", value: cycleStats.trades },
        { name: "Holds", value: cycleStats.holds },
        { name: "Vetoes", value: cycleStats.vetoes },
        { name: "Errors", value: cycleStats.errors },
      ].filter((d) => d.value > 0)
    : [];

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3">
        <h2 className="text-[13px] font-semibold text-text-primary">
          System Health
        </h2>
      </div>

      <div className="flex-1 px-5 space-y-5 overflow-auto pb-4">
        {/* Connection status */}
        <div className="space-y-0.5">
          <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider mb-2">
            Connections
          </p>
          <ConnectionRow label="API Server" status={apiStatus} />
          <ConnectionRow
            label="Trading Engine"
            status={health?.status === "ok" ? "connected" : apiStatus === "checking" ? "checking" : "disconnected"}
          />
        </div>

        {/* Key metrics */}
        <div className="space-y-2.5">
          <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">
            Runtime
          </p>
          <div className="flex justify-between">
            <span className="text-[11px] text-text-secondary">Total Cycles</span>
            <span className="text-[11px] font-mono text-text-primary">
              {cycleStats ? cycleStats.total_cycles : "--"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[11px] text-text-secondary">Current Regime</span>
            <span className="text-[11px] font-mono text-text-primary uppercase">
              {cycleStats?.current_regime || "--"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[11px] text-text-secondary">Cycle Counter</span>
            <span className="text-[11px] font-mono text-text-primary">
              {health ? health.cycle : "--"}
            </span>
          </div>
        </div>

        {/* Donut chart */}
        {donutData.length > 0 && (
          <div className="space-y-2">
            <p className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">
              Cycle Breakdown
            </p>
            <div className="flex items-center gap-4">
              <div className="w-[100px] h-[100px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={donutData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={28}
                      outerRadius={44}
                      strokeWidth={0}
                      animationDuration={600}
                      animationEasing="ease-out"
                    >
                      {donutData.map((_, idx) => (
                        <Cell
                          key={idx}
                          fill={DONUT_COLORS[idx % DONUT_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip content={<DonutTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Legend */}
              <div className="flex-1 space-y-1.5">
                {donutData.map((item, idx) => (
                  <div
                    key={item.name}
                    className="flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="inline-block w-2 h-2 rounded-full"
                        style={{
                          backgroundColor:
                            DONUT_COLORS[idx % DONUT_COLORS.length],
                        }}
                      />
                      <span className="text-[11px] text-text-secondary">
                        {item.name}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-text-primary">
                      {item.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {donutData.length === 0 && cycleStats === null && (
          <div className="flex flex-col items-center justify-center py-6 gap-2">
            <Layers size={20} className="text-text-tertiary" />
            <p className="text-[13px] text-text-tertiary">
              Waiting for cycle data
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
