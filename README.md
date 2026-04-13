# TradeBot — Multi-Agent Trading Floor

An AI-powered trading system modeled after an institutional trading desk. Specialist agents with distinct roles, isolated contexts, and adversarial checks — mirroring how a real trading floor operates.

## Architecture

```
┌──────────────────────────────────────────┐
│           THE TRADING DESK               │
│                                          │
│  Technical Analyst ─┐                    │
│  Sentiment Analyst ─┼─→ Strategist       │
│  Flow Analyst ──────┘      │             │
│                       Patience Engine    │
│                            │             │
│                       Risk Manager       │
│                            │             │
│                        Executor          │
│                            │             │
│                        Auditor           │
│                            │             │
│                     Playbook Update      │
└──────────────────────────────────────────┘
```

### Agents
- **Technical Analyst** — Charts + indicators + multimodal vision (AI sees charts like a human)
- **Sentiment Analyst** — News, X/Twitter (Grok), macro signals
- **Flow Analyst** — Order flow, volume, on-chain data
- **Strategist** — Reads all briefs, classifies regime, selects strategy
- **Risk Manager** — Hard veto power, enforces limits (default: VETO)
- **Executor** — Only agent touching the exchange API
- **Auditor** — Post-trade review, evolves the playbook

### Key Design Principles
- **No hardcoded rules** — AI IS the pattern recognizer
- **Analyst isolation** — Analysts can't see each other (prevents groupthink)
- **Patience Engine** — Default state is DO NOTHING. Must clear conviction threshold.
- **Self-improving** — Auditor updates the playbook after every trade

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 + FastAPI |
| LLMs | Claude (strategy/risk) + Grok (sentiment/X) |
| Exchange | Alpaca (paper trading) |
| Data | ccxt + pandas-ta + mplfinance |
| Database | PostgreSQL (Neon) |
| Dashboard | Next.js + TradingView Lightweight Charts |
| UI | Tailwind CSS + Framer Motion |
| Deploy | Docker Compose |

## Quick Start

```bash
# 1. Copy env template and add your API keys
cp .env.example .env

# 2. Start everything
docker compose up -d

# 3. Access dashboard
open http://localhost:3000

# 4. Backend API
open http://localhost:8000/docs
```

## Development

```bash
# Backend
cd backend
pip install -e ".[dev]"
python scripts/run_cycle.py  # Run one manual cycle

# Dashboard
cd dashboard
npm install
npm run dev
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | System health check |
| `/api/portfolio` | GET | Portfolio value + positions |
| `/api/positions` | GET | Open positions |
| `/api/trades` | GET | Trade history |
| `/api/playbook` | GET | Current strategy playbook |
| `/api/agent-logs` | GET | Recent agent outputs |
| `/api/run-cycle` | POST | Trigger one analysis cycle |
| `/api/start` | POST | Start continuous loop |
| `/api/stop` | POST | Stop continuous loop |
| `/ws/agent-feed` | WS | Real-time agent reasoning stream |
| `/ws/market-data` | WS | Live ticker data for charts |
