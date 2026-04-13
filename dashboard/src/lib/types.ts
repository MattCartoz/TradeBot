/** TypeScript types matching the backend Pydantic models. */

export interface AgentEvent {
  type: string;
  timestamp: string;
  cycle: number;
  [key: string]: unknown;
}

export interface AnalystBriefEvent extends AgentEvent {
  type: "analyst_brief";
  agent: string;
  conviction: number;
  regime: string;
  reasoning: string;
}

export interface StrategyEvent extends AgentEvent {
  type: "strategy_decision";
  regime: string;
  action: string;
  symbol: string;
  conviction: number;
  reasoning: string;
}

export interface RiskEvent extends AgentEvent {
  type: "risk_assessment";
  decision: string;
  reasoning: string;
  veto_reasons: string[];
}

export interface TradeEvent extends AgentEvent {
  type: "trade_executed";
  symbol: string;
  side: string;
  quantity: number;
  price: number;
}

export interface Position {
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  market_value: number;
}

export interface Trade {
  id: string;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  pnl: number | null;
  pnl_pct: number | null;
  status: string;
  opened_at: string;
  closed_at: string | null;
  post_mortem: Record<string, unknown> | null;
}

export interface TickerData {
  symbol: string;
  bid: number;
  ask: number;
  last: number;
  volume: number;
  timestamp: string;
}

export interface Portfolio {
  value: number;
  cash: number;
  drawdown_pct: number;
  peak_value: number;
  risk_pct: number;
  positions: Record<string, Position>;
}
