"use client";

import { useEffect, useState } from "react";
import {
  ArrowRightLeft,
  PauseCircle,
  ShieldOff,
  AlertTriangle,
  Clock,
} from "lucide-react";
import { API_URL } from "@/lib/utils";

interface CycleEntry {
  cycle: number;
  timestamp: string;
  action: "trade" | "hold" | "vetoed" | "error";
  reasoning: string;
  regime: string;
}

const actionConfig: Record<
  CycleEntry["action"],
  { icon: React.ReactNode; label: string; classes: string }
> = {
  trade: {
    icon: <ArrowRightLeft size={11} />,
    label: "Trade",
    classes: "bg-profit/10 text-profit",
  },
  hold: {
    icon: <PauseCircle size={11} />,
    label: "Hold",
    classes: "bg-accent/10 text-accent",
  },
  vetoed: {
    icon: <ShieldOff size={11} />,
    label: "Vetoed",
    classes: "bg-warning/10 text-warning",
  },
  error: {
    icon: <AlertTriangle size={11} />,
    label: "Error",
    classes: "bg-loss/10 text-loss",
  },
};

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function CycleRow({ entry }: { entry: CycleEntry }) {
  const config = actionConfig[entry.action] || actionConfig.error;

  return (
    <div className="flex gap-3 py-3 border-b border-border last:border-b-0 group">
      {/* Timeline dot */}
      <div className="flex flex-col items-center pt-0.5">
        <div
          className={`flex items-center justify-center w-6 h-6 rounded-full ${config.classes}`}
        >
          {config.icon}
        </div>
        <div className="flex-1 w-px bg-border mt-1.5" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[12px] font-semibold text-text-primary">
              #{entry.cycle}
            </span>
            <span
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[var(--radius-sm)] text-[10px] font-medium ${config.classes}`}
            >
              {config.label}
            </span>
            {entry.regime && (
              <span className="text-[10px] font-medium text-text-tertiary uppercase tracking-wider">
                {entry.regime}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 text-text-tertiary">
            <Clock size={10} />
            <span className="text-[10px] font-mono">
              {formatTimestamp(entry.timestamp)}
            </span>
          </div>
        </div>

        {entry.reasoning && (
          <p className="text-[11px] text-text-secondary leading-relaxed line-clamp-2">
            {entry.reasoning}
          </p>
        )}
      </div>
    </div>
  );
}

export function CycleActivity() {
  const [cycles, setCycles] = useState<CycleEntry[]>([]);

  useEffect(() => {
    const fetchCycles = async () => {
      try {
        const res = await fetch(`${API_URL}/api/recent-cycles`);
        if (res.ok) setCycles(await res.json());
      } catch {
        /* backend offline */
      }
    };
    fetchCycles();
    const interval = setInterval(fetchCycles, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3 flex items-center justify-between">
        <h2 className="text-[13px] font-semibold text-text-primary">
          Cycle Activity
        </h2>
        {cycles.length > 0 && (
          <span className="text-[10px] font-mono text-text-tertiary">
            {cycles.length} recent
          </span>
        )}
      </div>

      <div className="flex-1 overflow-auto px-5 pb-3">
        {cycles.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2">
            <Clock size={20} className="text-text-tertiary" />
            <p className="text-[13px] text-text-tertiary">
              No cycles recorded yet
            </p>
          </div>
        ) : (
          <div>
            {cycles.map((entry) => (
              <CycleRow key={`${entry.cycle}-${entry.timestamp}`} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
