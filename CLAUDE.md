# TradeBot — Development Guidelines

## Core Design Principle: AI Judgment, Not Hardcoded Rules

**This is the single most important rule for this project.**

Traditional trading bots (freqtrade, etc.) hardcode rules:
`if RSI > 70: sell` or `trailing_stop: 4%` or `roi_table: {60: 0.01}`.

We do NOT do this. The AI IS the strategy. Every decision — entry, exit,
stop placement, position sizing, profit taking, regime classification —
is made by an AI agent reasoning about context, not by `if/else` logic.

### What this means in practice:

- **NO hardcoded indicator thresholds** — Don't write `if rsi > 70`.
  Give the AI the RSI value and let it decide what it means in context.
- **NO hardcoded stop-loss percentages** — The Position Manager agent
  dynamically adjusts stops based on volatility, regime, and thesis.
- **NO hardcoded ROI/exit tables** — The AI decides when to take profit
  based on momentum, regime, and risk/reward from current price.
- **NO hardcoded entry rules** — The Technical Analyst sees charts and
  data; the Strategist decides whether to act.
- **Computed math is OK** — We DO compute RSI, MACD, Bollinger Bands
  deterministically. We do NOT hardcode what those values mean.
- **Config thresholds are guardrails, not strategy** — The Patience
  Engine's conviction threshold (0.7) is a safety guardrail to prevent
  overtrading. The AI decides the conviction score. Similarly, max
  drawdown limits are safety rails, not trading logic.

### Agent Architecture

Each agent has a distinct role and isolated context:
- **Technical Analyst** — Charts (vision) + indicators + OHLCV + order book
- **Sentiment Analyst** — Fear & Greed + X/Twitter (Grok) + FRED macro
- **Flow Analyst** — Order book depth + volume + on-chain (DeFiLlama)
- **Bull/Bear Debate** — Adversarial arguments before strategy decision
- **Strategist** — Reads all briefs + debate, classifies regime, proposes action
- **Position Manager** — AI-driven exit management for open positions
- **Risk Manager** — Hard veto power, but AI-reasoned (not rule-based)
- **Executor** — Deterministic order submission (the one exception)
- **Auditor** — Post-mortem analysis, evolves the playbook

### Tech Stack
- Backend: Python 3.11 + FastAPI
- LLMs: Claude (strategy/risk/analysis) + Grok (X sentiment)
- Exchange: Alpaca (paper trading)
- Data: ccxt + pandas-ta + mplfinance
- Database: PostgreSQL
- Dashboard: Next.js + TradingView Lightweight Charts
- Notifications: Telegram bot
- Deploy: Docker Compose

### Exchange
- Alpaca paper trading (BTC/USD, ETH/USD)
- Symbols configurable in config/settings.yaml
