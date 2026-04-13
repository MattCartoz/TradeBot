"""Semantic Memory — Tier 3: the evolving strategy playbook.

The playbook is the system's accumulated knowledge — strategies that work
in different regimes, rules the Auditor has derived from trade post-mortems,
and confidence scores for various setups.

Stored as versioned JSON so you can diff strategy evolution over time.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from src.contracts import PlaybookUpdate

logger = logging.getLogger(__name__)

DEFAULT_PLAYBOOK_PATH = Path("config/playbook.json")


class SemanticMemory:
    """Manages the strategy playbook — the system's learned knowledge."""

    def __init__(self, playbook_path: str | Path | None = None):
        self.path = Path(playbook_path) if playbook_path else DEFAULT_PLAYBOOK_PATH
        self._playbook: dict = {}

    def load(self) -> dict:
        """Load the current playbook."""
        if self.path.exists():
            self._playbook = json.loads(self.path.read_text())
        else:
            self._playbook = self._default_playbook()
            self.save()
        logger.info(
            "Loaded playbook v%s with %d strategies",
            self._playbook.get("version", "0"),
            len(self._playbook.get("strategies", {})),
        )
        return self._playbook

    def get_playbook(self) -> dict:
        if not self._playbook:
            return self.load()
        return self._playbook

    def apply_updates(self, updates: list[PlaybookUpdate]) -> None:
        """Apply Auditor-recommended updates to the playbook."""
        if not updates:
            return

        # Backup before modifying
        self._backup()

        if "update_history" not in self._playbook:
            self._playbook["update_history"] = []

        for update in updates:
            self._playbook["update_history"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "type": update.update_type,
                "target": update.target,
                "change": update.change,
                "reasoning": update.reasoning,
            })

            # Apply to the rules section
            if "learned_rules" not in self._playbook:
                self._playbook["learned_rules"] = []

            self._playbook["learned_rules"].append({
                "added": datetime.utcnow().isoformat(),
                "rule": update.change,
                "source": update.reasoning,
            })

            # Actually modify strategies if the update targets one
            strategies = self._playbook.get("strategies", {})
            target = update.target.lower().replace(" ", "_")

            if update.update_type == "adjust_threshold" and target in strategies:
                # Update confidence score based on auditor feedback
                strategies[target]["last_auditor_note"] = update.change
                strategies[target]["last_updated"] = datetime.utcnow().isoformat()
            elif update.update_type == "modify_strategy" and target in strategies:
                # Modify an existing strategy's description or parameters
                strategies[target]["description"] = update.change
                strategies[target]["last_updated"] = datetime.utcnow().isoformat()
            elif update.update_type == "add_rule":
                # New rules get added to learned_rules (already done above)
                # but also flag the target strategy if it exists
                if target in strategies:
                    if "notes" not in strategies[target]:
                        strategies[target]["notes"] = []
                    strategies[target]["notes"].append(update.change)

        # Bump version
        version = self._playbook.get("version", 0)
        self._playbook["version"] = version + 1
        self._playbook["last_updated"] = datetime.utcnow().isoformat()

        self.save()
        logger.info(
            "Applied %d playbook updates → v%d",
            len(updates), self._playbook["version"],
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._playbook, indent=2, default=str))

    def _backup(self) -> None:
        if self.path.exists():
            backup_dir = self.path.parent / "playbook_history"
            backup_dir.mkdir(exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(self.path, backup_dir / f"playbook_{ts}.json")

    @staticmethod
    def _default_playbook() -> dict:
        return {
            "version": 1,
            "created": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
            "strategies": {
                "trend_following_breakout": {
                    "regime": "trending_up",
                    "description": "Buy breakouts above key resistance in confirmed uptrends",
                    "entry": "Price breaks above resistance with volume confirmation",
                    "exit": "Trailing stop at 2x ATR below swing high",
                    "risk_reward": 3.0,
                    "confidence": 0.5,
                },
                "trend_following_pullback": {
                    "regime": "trending_up",
                    "description": "Buy pullbacks to EMA support in uptrends",
                    "entry": "Price pulls back to EMA20/50 and bounces with bullish candle",
                    "exit": "Target previous high, stop below pullback low",
                    "risk_reward": 2.5,
                    "confidence": 0.5,
                },
                "mean_reversion_ranging": {
                    "regime": "ranging",
                    "description": "Buy at range support, sell at range resistance",
                    "entry": "Price touches lower Bollinger Band with RSI < 35",
                    "exit": "Target middle or upper BB, stop below range low",
                    "risk_reward": 2.0,
                    "confidence": 0.5,
                },
                "volatility_breakout": {
                    "regime": "volatile",
                    "description": "Trade volatility expansions after compression",
                    "entry": "Bollinger Band squeeze followed by expansion with volume",
                    "exit": "Target 2x ATR move, tight stop at entry",
                    "risk_reward": 2.0,
                    "confidence": 0.4,
                },
                "stay_flat": {
                    "regime": "dead",
                    "description": "Do nothing in dead markets. Patience is a strategy.",
                    "entry": "None — wait for regime change",
                    "exit": "N/A",
                    "risk_reward": 0,
                    "confidence": 1.0,
                },
            },
            "learned_rules": [],
            "update_history": [],
        }
