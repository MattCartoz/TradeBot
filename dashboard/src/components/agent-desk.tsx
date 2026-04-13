"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAgentFeed } from "@/hooks/use-websocket";
import type { AgentEvent } from "@/lib/types";

const AGENT_ICONS: Record<string, string> = {
  cycle_start: "\u23F1",
  analyst_brief: "\uD83D\uDCCA",
  analyst_phase: "\uD83D\uDD0D",
  strategy_decision: "\uD83C\uDFAF",
  patience_block: "\u23F8",
  risk_assessment: "\uD83D\uDEE1\uFE0F",
  trade_executed: "\u26A1",
  cycle_error: "\u26A0\uFE0F",
  agent_error: "\u274C",
};

const AGENT_COLORS: Record<string, string> = {
  technical_analyst: "text-cyan",
  sentiment_analyst: "text-orange",
  flow_analyst: "text-purple",
  strategist: "text-profit",
  risk_manager: "text-loss",
  executor: "text-foreground",
};

function formatEvent(event: AgentEvent): { title: string; detail: string; color: string } {
  const type = event.type;

  if (type === "cycle_start") {
    return {
      title: `Cycle #${event.cycle} Starting`,
      detail: "",
      color: "text-muted",
    };
  }

  if (type === "analyst_brief") {
    const e = event as { agent: string; conviction: number; regime: string; reasoning: string };
    return {
      title: e.agent.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      detail: `Regime: ${e.regime} | Conviction: ${e.conviction?.toFixed(2)} — ${e.reasoning}`,
      color: AGENT_COLORS[e.agent] || "text-foreground",
    };
  }

  if (type === "strategy_decision") {
    const e = event as { regime: string; action: string; symbol: string; conviction: number; reasoning: string };
    const passed = e.conviction >= 0.7;
    return {
      title: "Strategist",
      detail: `Regime: ${e.regime} | Action: ${e.action?.toUpperCase()} ${e.symbol} | Conviction: ${e.conviction?.toFixed(2)} ${passed ? "\u2705" : "\u274C"} — ${e.reasoning}`,
      color: "text-profit",
    };
  }

  if (type === "risk_assessment") {
    const e = event as { decision: string; reasoning: string; veto_reasons: string[] };
    const approved = e.decision === "approved";
    return {
      title: "Risk Manager",
      detail: `${approved ? "\u2705 APPROVED" : "\u274C VETOED"} — ${approved ? e.reasoning : e.veto_reasons?.join("; ")}`,
      color: approved ? "text-profit" : "text-loss",
    };
  }

  if (type === "patience_block") {
    return {
      title: "Patience Engine",
      detail: `\u23F8 ${(event as { reason: string }).reason}`,
      color: "text-orange",
    };
  }

  if (type === "trade_executed") {
    const e = event as { symbol: string; side: string; quantity: number; price: number };
    return {
      title: "Executor",
      detail: `${e.side?.toUpperCase()} ${e.quantity} ${e.symbol} @ $${e.price?.toLocaleString()}`,
      color: "text-cyan",
    };
  }

  return {
    title: type,
    detail: JSON.stringify(event),
    color: "text-muted",
  };
}

export function AgentDesk() {
  const { events, connected } = useAgentFeed();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 border-b border-card-border">
        <h2 className="text-sm font-semibold tracking-wide">AGENT DESK</h2>
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${connected ? "bg-profit" : "bg-loss"}`}
          />
          <span className="text-xs text-muted">
            {connected ? "Live" : "Disconnected"}
          </span>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-2 space-y-1"
      >
        {events.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-muted">
            <p className="text-sm">Waiting for trading cycle...</p>
            <p className="text-xs mt-1">
              Start the loop via POST /api/start or click Run Cycle
            </p>
          </div>
        )}

        <AnimatePresence initial={false}>
          {events.map((event, i) => {
            const { title, detail, color } = formatEvent(event);
            const icon = AGENT_ICONS[event.type] || "\u2022";

            return (
              <motion.div
                key={`${event.timestamp}-${i}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="py-1.5 border-b border-card-border/50 last:border-0"
              >
                <div className="flex items-start gap-2">
                  <span className="text-sm flex-shrink-0 mt-0.5">{icon}</span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold ${color}`}>
                        {title}
                      </span>
                      <span className="text-[10px] font-mono text-muted">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    {detail && (
                      <p className="text-xs text-muted/80 mt-0.5 leading-relaxed truncate">
                        {detail}
                      </p>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
