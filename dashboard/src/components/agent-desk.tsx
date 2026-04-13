"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart3,
  Search,
  Target,
  Pause,
  ShieldCheck,
  ShieldX,
  Zap,
  AlertTriangle,
  XCircle,
  Circle,
  FileText,
  LogOut,
  BookOpen,
  Database,
  MessageSquare,
  ArrowUpDown,
  ScissorsLineDashed,
  Trash2,
} from "lucide-react";
import { useAgentFeed } from "@/hooks/use-websocket";
import type { AgentEvent } from "@/lib/types";

const AGENT_ICONS: Record<string, React.ReactNode> = {
  cycle_start: <Circle size={12} />,
  analyst_brief: <BarChart3 size={12} />,
  analyst_phase: <Search size={12} />,
  data_collected: <Database size={12} />,
  strategy_decision: <Target size={12} />,
  patience_block: <Pause size={12} />,
  risk_assessment: <ShieldCheck size={12} />,
  trade_executed: <Zap size={12} />,
  position_closed: <LogOut size={12} />,
  post_mortem: <FileText size={12} />,
  playbook_updated: <BookOpen size={12} />,
  stop_loss_triggered: <AlertTriangle size={12} />,
  take_profit_triggered: <Target size={12} />,
  debate_complete: <MessageSquare size={12} />,
  stop_adjusted: <ArrowUpDown size={12} />,
  partial_take: <ScissorsLineDashed size={12} />,
  position_manager_close: <LogOut size={12} />,
  stale_orders_cancelled: <Trash2 size={12} />,
  cycle_error: <AlertTriangle size={12} />,
  agent_error: <XCircle size={12} />,
};

const AGENT_COLORS: Record<string, string> = {
  technical_analyst: "text-accent",
  sentiment_analyst: "text-warning",
  flow_analyst: "text-[#bf5af2]",
  strategist: "text-profit",
  risk_manager: "text-loss",
  executor: "text-text-primary",
};

function formatEvent(event: AgentEvent): {
  title: string;
  detail: string;
  color: string;
  icon: React.ReactNode;
} {
  const type = event.type;
  const icon = AGENT_ICONS[type] || <Circle size={12} />;

  if (type === "cycle_start") {
    return { title: `Cycle ${event.cycle}`, detail: "", color: "text-text-tertiary", icon };
  }

  if (type === "analyst_brief") {
    const e = event as unknown as { agent: string; conviction: number; regime: string; reasoning: string };
    return {
      title: e.agent.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      detail: `${e.regime}  ${e.conviction?.toFixed(2)} conviction  ${e.reasoning}`,
      color: AGENT_COLORS[e.agent] || "text-text-primary",
      icon,
    };
  }

  if (type === "strategy_decision") {
    const e = event as unknown as { regime: string; action: string; symbol: string; conviction: number; reasoning: string };
    return {
      title: "Strategist",
      detail: `${e.action?.toUpperCase()} ${e.symbol}  ${e.conviction?.toFixed(2)} conviction  ${e.reasoning}`,
      color: "text-profit",
      icon: <Target size={12} />,
    };
  }

  if (type === "risk_assessment") {
    const e = event as unknown as { decision: string; reasoning: string; veto_reasons: string[] };
    const approved = e.decision === "approved";
    return {
      title: "Risk Manager",
      detail: approved ? e.reasoning : e.veto_reasons?.join(". "),
      color: approved ? "text-profit" : "text-loss",
      icon: approved ? <ShieldCheck size={12} /> : <ShieldX size={12} />,
    };
  }

  if (type === "patience_block") {
    return {
      title: "Patience Engine",
      detail: (event as unknown as { reason: string }).reason,
      color: "text-text-secondary",
      icon: <Pause size={12} />,
    };
  }

  if (type === "trade_executed") {
    const e = event as unknown as { symbol: string; side: string; quantity: number; price: number };
    return {
      title: "Executed",
      detail: `${e.side?.toUpperCase()} ${e.quantity} ${e.symbol} @ $${e.price?.toLocaleString()}`,
      color: "text-accent",
      icon: <Zap size={12} />,
    };
  }

  if (type === "position_closed") {
    const e = event as unknown as { symbol: string; pnl: number; pnl_pct: number; reason: string };
    const win = e.pnl >= 0;
    return {
      title: "Position Closed",
      detail: `${e.symbol} ${e.reason}  $${e.pnl?.toFixed(2)} (${e.pnl_pct?.toFixed(1)}%)`,
      color: win ? "text-profit" : "text-loss",
      icon: <LogOut size={12} />,
    };
  }

  if (type === "post_mortem") {
    const e = event as unknown as { symbol: string; outcome: string; lessons: string[] };
    return {
      title: "Auditor Review",
      detail: `${e.symbol} ${e.outcome}  ${e.lessons?.[0] || ""}`,
      color: "text-text-secondary",
      icon: <FileText size={12} />,
    };
  }

  if (type === "playbook_updated") {
    const e = event as unknown as { updates: number; new_version: number };
    return {
      title: "Playbook Updated",
      detail: `${e.updates} new rules applied, now v${e.new_version}`,
      color: "text-accent",
      icon: <BookOpen size={12} />,
    };
  }

  if (type === "data_collected") {
    const e = event as unknown as { symbols: string[]; chart_images: number; indicators: number; fear_greed: string };
    return {
      title: "Data Collected",
      detail: `${e.chart_images} charts, ${e.indicators} indicator sets, F&G: ${e.fear_greed}`,
      color: "text-text-tertiary",
      icon: <Database size={12} />,
    };
  }

  if (type === "debate_complete") {
    const e = event as unknown as { consensus: string; agreement: number; bull_conviction: number; bear_conviction: number };
    return {
      title: "Bull/Bear Debate",
      detail: `Consensus: ${e.consensus}  Agreement: ${e.agreement?.toFixed(2)}  Bull: ${e.bull_conviction?.toFixed(2)} vs Bear: ${e.bear_conviction?.toFixed(2)}`,
      color: "text-text-secondary",
      icon: <MessageSquare size={12} />,
    };
  }

  if (type === "stop_adjusted") {
    const e = event as unknown as { symbol: string; new_stop: number; reasoning: string };
    return {
      title: "Stop Adjusted",
      detail: `${e.symbol} new stop: $${e.new_stop?.toLocaleString()}  ${e.reasoning}`,
      color: "text-warning",
      icon: <ArrowUpDown size={12} />,
    };
  }

  if (type === "position_manager_close") {
    const e = event as unknown as { symbol: string; reasoning: string };
    return {
      title: "Position Manager Exit",
      detail: `${e.symbol}  ${e.reasoning}`,
      color: "text-loss",
      icon: <LogOut size={12} />,
    };
  }

  return {
    title: type.replace(/_/g, " "),
    detail: "",
    color: "text-text-tertiary",
    icon,
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
      <div className="flex items-center justify-between px-5 py-3">
        <h2 className="text-[13px] font-semibold text-text-primary">
          Agent Activity
        </h2>
        <div className="flex items-center gap-1.5">
          <span
            className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-profit" : "bg-loss"}`}
          />
          <span className="text-[11px] text-text-tertiary">
            {connected ? "Connected" : "Offline"}
          </span>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 pb-4">
        {events.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-2">
            <p className="text-[13px] text-text-tertiary">Waiting for activity</p>
            <p className="text-[11px] text-text-tertiary/60">
              Run a cycle to see agent reasoning here
            </p>
          </div>
        )}

        <AnimatePresence initial={false}>
          {events.map((event, i) => {
            const { title, detail, color, icon } = formatEvent(event);

            return (
              <motion.div
                key={`${event.timestamp}-${i}`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.15 }}
                className="py-2.5 border-b border-border last:border-0"
              >
                <div className="flex items-start gap-2.5">
                  <span className={`mt-0.5 flex-shrink-0 ${color}`}>
                    {icon}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-[12px] font-medium ${color}`}>
                        {title}
                      </span>
                      <span className="text-[10px] font-mono text-text-tertiary">
                        {new Date(event.timestamp).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                        })}
                      </span>
                    </div>
                    {detail && (
                      <p className="text-[11px] text-text-secondary mt-0.5 leading-relaxed line-clamp-2">
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
