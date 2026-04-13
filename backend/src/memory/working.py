"""Working Memory — Tier 1: in-memory state with crash recovery.

Current positions, open orders, live market state, cycle state.
Persisted to JSON on disk so we can recover after a restart.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

WORKING_MEMORY_FILE = Path("data/working_memory.json")


@dataclass
class Position:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    opened_at: str
    stop_loss: float | None = None
    take_profit: float | None = None
    trade_id: str = ""
    analyst_briefs: list[dict] = field(default_factory=list)
    strategy_decision: dict = field(default_factory=dict)
    risk_assessment: dict = field(default_factory=dict)


class WorkingMemory:
    """In-memory state for the current trading session."""

    def __init__(self):
        self.positions: dict[str, Position] = {}  # symbol -> Position
        self.portfolio_value: float = 0.0
        self.cash_balance: float = 0.0
        self.peak_portfolio_value: float = 0.0
        self.current_drawdown_pct: float = 0.0
        self.last_cycle_time: datetime | None = None
        self.cycle_count: int = 0
        self.agent_logs: list[dict] = []  # Rolling buffer of recent agent outputs

    def update_portfolio(self, value: float, cash: float) -> None:
        self.portfolio_value = value
        self.cash_balance = cash
        if value > self.peak_portfolio_value:
            self.peak_portfolio_value = value
        if self.peak_portfolio_value > 0:
            self.current_drawdown_pct = (
                (self.peak_portfolio_value - value) / self.peak_portfolio_value * 100
            )

    def open_position(self, position: Position) -> None:
        self.positions[position.symbol] = position
        logger.info("Opened position: %s %s %.6f @ $%.2f",
                     position.side, position.symbol, position.quantity, position.entry_price)

    def close_position(self, symbol: str) -> Position | None:
        pos = self.positions.pop(symbol, None)
        if pos:
            logger.info("Closed position: %s", symbol)
        return pos

    def add_agent_log(self, agent_name: str, output: dict, cycle: int) -> None:
        """Add an agent output to the rolling log (for dashboard streaming)."""
        self.agent_logs.append({
            "agent": agent_name,
            "cycle": cycle,
            "timestamp": datetime.utcnow().isoformat(),
            "output": output,
        })
        # Keep last 200 entries
        if len(self.agent_logs) > 200:
            self.agent_logs = self.agent_logs[-200:]

    def save_to_disk(self) -> None:
        """Persist state to JSON for crash recovery (atomic write)."""
        WORKING_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "positions": {k: vars(v) for k, v in self.positions.items()},
            "portfolio_value": self.portfolio_value,
            "cash_balance": self.cash_balance,
            "peak_portfolio_value": self.peak_portfolio_value,
            "current_drawdown_pct": self.current_drawdown_pct,
            "cycle_count": self.cycle_count,
            "last_cycle_time": self.last_cycle_time.isoformat() if self.last_cycle_time else None,
        }
        # Atomic write: write to temp file, then rename.
        # This prevents corruption if the process is killed mid-write.
        tmp_path = WORKING_MEMORY_FILE.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, default=str))
        tmp_path.replace(WORKING_MEMORY_FILE)

    def load_from_disk(self) -> None:
        """Restore state from disk after restart."""
        if not WORKING_MEMORY_FILE.exists():
            return
        try:
            data = json.loads(WORKING_MEMORY_FILE.read_text())
            self.portfolio_value = data.get("portfolio_value", 0)
            self.cash_balance = data.get("cash_balance", 0)
            self.peak_portfolio_value = data.get("peak_portfolio_value", 0)
            self.current_drawdown_pct = data.get("current_drawdown_pct", 0)
            self.cycle_count = data.get("cycle_count", 0)
            if data.get("last_cycle_time"):
                self.last_cycle_time = datetime.fromisoformat(data["last_cycle_time"])
            for symbol, pos_data in data.get("positions", {}).items():
                self.positions[symbol] = Position(**pos_data)
            logger.info("Restored working memory: %d positions, cycle #%d",
                         len(self.positions), self.cycle_count)
        except Exception as e:
            logger.error("Failed to load working memory: %s", e)
