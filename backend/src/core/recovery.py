"""Crash Recovery — reconcile saved working memory with actual exchange state.

On startup, the bot may have crashed mid-cycle. This module detects that
scenario, fetches the real exchange positions, compares them against the
persisted working memory, and updates memory to match reality.
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel, Field

from src.exchange.base import BaseExchange
from src.memory.working import Position, WorkingMemory

logger = logging.getLogger(__name__)


class RecoveryReport(BaseModel):
    """Summary of what the recovery process found and fixed."""

    recovered_positions: int = Field(
        description="Total number of positions successfully reconciled"
    )
    orphaned_positions: list[str] = Field(
        default_factory=list,
        description="Symbols found on exchange but missing from working memory",
    )
    stale_positions: list[str] = Field(
        default_factory=list,
        description="Symbols in working memory but no longer on exchange",
    )
    actions_taken: list[str] = Field(
        default_factory=list,
        description="Human-readable log of every reconciliation action",
    )
    recovered_at: datetime = Field(default_factory=datetime.utcnow)


class RecoveryManager:
    """Reconcile persisted working memory with live exchange state after restart."""

    async def recover(
        self, working: WorkingMemory, exchange: BaseExchange
    ) -> RecoveryReport:
        """Run the full recovery sequence.

        Steps:
            1. Load working memory from disk (if a state file exists).
            2. Fetch actual open positions from the exchange.
            3. Compare the two — find orphaned and stale positions.
            4. Update working memory to match exchange reality.
            5. Persist the corrected state back to disk.
            6. Return a report of everything that changed.

        Args:
            working: The WorkingMemory instance (may already be loaded or empty).
            exchange: An initialized exchange connector.

        Returns:
            A RecoveryReport describing what was reconciled.
        """
        actions: list[str] = []

        # --- Step 1: Load persisted state -----------------------------------
        working.load_from_disk()
        memory_symbols = set(working.positions.keys())
        actions.append(
            f"Loaded working memory from disk: {len(memory_symbols)} position(s)"
        )
        logger.info(
            "Recovery: loaded %d position(s) from disk: %s",
            len(memory_symbols),
            sorted(memory_symbols) if memory_symbols else "(none)",
        )

        # --- Step 2: Fetch live exchange positions --------------------------
        exchange_positions = await exchange.get_positions()
        exchange_by_symbol = _index_exchange_positions(exchange_positions)
        exchange_symbols = set(exchange_by_symbol.keys())
        actions.append(
            f"Fetched {len(exchange_symbols)} position(s) from exchange"
        )
        logger.info(
            "Recovery: exchange reports %d position(s): %s",
            len(exchange_symbols),
            sorted(exchange_symbols) if exchange_symbols else "(none)",
        )

        # --- Step 3: Compare ------------------------------------------------
        orphaned_symbols = sorted(exchange_symbols - memory_symbols)
        stale_symbols = sorted(memory_symbols - exchange_symbols)
        common_symbols = sorted(memory_symbols & exchange_symbols)

        # --- Step 4a: Adopt orphaned positions (on exchange, not in memory) --
        for symbol in orphaned_symbols:
            pos_data = exchange_by_symbol[symbol]
            position = _exchange_position_to_memory(symbol, pos_data)
            working.open_position(position)
            msg = (
                f"Adopted orphaned position: {symbol} "
                f"({position.side} {position.quantity} @ ${position.entry_price:.2f})"
            )
            actions.append(msg)
            logger.warning("Recovery: %s", msg)

        # --- Step 4b: Remove stale positions (in memory, not on exchange) ----
        for symbol in stale_symbols:
            stale_pos = working.close_position(symbol)
            msg = f"Removed stale position: {symbol}"
            if stale_pos:
                msg += (
                    f" (was {stale_pos.side} {stale_pos.quantity} "
                    f"@ ${stale_pos.entry_price:.2f})"
                )
            actions.append(msg)
            logger.warning("Recovery: %s", msg)

        # --- Step 4c: Reconcile common positions ----------------------------
        for symbol in common_symbols:
            pos_data = exchange_by_symbol[symbol]
            mem_pos = working.positions[symbol]
            discrepancies = _check_discrepancies(mem_pos, pos_data)
            if discrepancies:
                _apply_exchange_truth(mem_pos, pos_data)
                msg = f"Updated position {symbol}: {'; '.join(discrepancies)}"
                actions.append(msg)
                logger.info("Recovery: %s", msg)

        # --- Step 5: Update portfolio and persist ---------------------------
        try:
            portfolio_value = await exchange.get_portfolio_value()
            balances = await exchange.get_balance()
            cash = balances.get("USD", balances.get("USDT", 0.0))
            working.update_portfolio(portfolio_value, cash)
            actions.append(
                f"Updated portfolio: value=${portfolio_value:,.2f}, cash=${cash:,.2f}"
            )
        except Exception as exc:
            msg = f"Could not refresh portfolio value: {exc}"
            actions.append(msg)
            logger.error("Recovery: %s", msg)

        working.save_to_disk()
        actions.append("Persisted corrected working memory to disk")

        # --- Step 6: Build report -------------------------------------------
        recovered_count = len(common_symbols) + len(orphaned_symbols)

        report = RecoveryReport(
            recovered_positions=recovered_count,
            orphaned_positions=orphaned_symbols,
            stale_positions=stale_symbols,
            actions_taken=actions,
        )

        logger.info(
            "Recovery complete: %d recovered, %d orphaned, %d stale, %d actions",
            report.recovered_positions,
            len(report.orphaned_positions),
            len(report.stale_positions),
            len(report.actions_taken),
        )

        return report


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _index_exchange_positions(positions: list[dict]) -> dict[str, dict]:
    """Index exchange position dicts by symbol for O(1) lookup."""
    indexed: dict[str, dict] = {}
    for pos in positions:
        symbol = pos.get("symbol", "")
        if symbol:
            indexed[symbol] = pos
    return indexed


def _exchange_position_to_memory(symbol: str, pos_data: dict) -> Position:
    """Convert an exchange position dict into a WorkingMemory Position."""
    return Position(
        symbol=symbol,
        side=pos_data.get("side", "long"),
        quantity=float(pos_data.get("quantity", pos_data.get("size", 0.0))),
        entry_price=float(pos_data.get("entry_price", pos_data.get("avg_price", 0.0))),
        opened_at=pos_data.get("opened_at", datetime.utcnow().isoformat()),
        stop_loss=pos_data.get("stop_loss"),
        take_profit=pos_data.get("take_profit"),
        trade_id=pos_data.get("trade_id", pos_data.get("id", "")),
    )


def _check_discrepancies(mem_pos: Position, exchange_data: dict) -> list[str]:
    """Check if a memory position diverges from exchange truth.

    Returns a list of human-readable discrepancy descriptions (empty = match).
    """
    discrepancies: list[str] = []

    exchange_qty = float(
        exchange_data.get("quantity", exchange_data.get("size", mem_pos.quantity))
    )
    if abs(mem_pos.quantity - exchange_qty) > 1e-8:
        discrepancies.append(
            f"quantity {mem_pos.quantity} -> {exchange_qty}"
        )

    exchange_side = exchange_data.get("side", mem_pos.side)
    if mem_pos.side != exchange_side:
        discrepancies.append(f"side '{mem_pos.side}' -> '{exchange_side}'")

    exchange_entry = float(
        exchange_data.get("entry_price", exchange_data.get("avg_price", mem_pos.entry_price))
    )
    if abs(mem_pos.entry_price - exchange_entry) > 0.01:
        discrepancies.append(
            f"entry_price {mem_pos.entry_price} -> {exchange_entry}"
        )

    return discrepancies


def _apply_exchange_truth(mem_pos: Position, exchange_data: dict) -> None:
    """Overwrite memory position fields with exchange reality."""
    if "quantity" in exchange_data or "size" in exchange_data:
        mem_pos.quantity = float(
            exchange_data.get("quantity", exchange_data.get("size", mem_pos.quantity))
        )
    if "side" in exchange_data:
        mem_pos.side = exchange_data["side"]
    if "entry_price" in exchange_data or "avg_price" in exchange_data:
        mem_pos.entry_price = float(
            exchange_data.get("entry_price", exchange_data.get("avg_price", mem_pos.entry_price))
        )
    if "stop_loss" in exchange_data:
        mem_pos.stop_loss = exchange_data.get("stop_loss")
    if "take_profit" in exchange_data:
        mem_pos.take_profit = exchange_data.get("take_profit")
