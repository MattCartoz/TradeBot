"""The Patience Engine — the system's default state is DO NOTHING.

Every cycle that results in no trade is a SUCCESS, not a failure.
The system must produce overwhelming evidence to justify action.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.contracts import StrategyDecision
from src.core.config import PatienceConfig

logger = logging.getLogger(__name__)


@dataclass
class PatienceState:
    """Tracks trade frequency and cooldown state."""

    trades_today: int = 0
    last_trade_time: datetime | None = None
    day_start: datetime = field(default_factory=datetime.utcnow)


class PatienceEngine:
    """Gatekeeper that prevents overtrading.

    The Strategist must produce a conviction score that clears the threshold,
    AND the cooldown period must have elapsed, AND we can't have exceeded
    the daily trade limit. Only then does the Risk Manager even get consulted.
    """

    def __init__(self, config: PatienceConfig):
        self.config = config
        self.state = PatienceState()

    def should_proceed(self, decision: StrategyDecision) -> tuple[bool, str]:
        """Check whether this decision should proceed to the Risk Manager.

        Returns:
            (allowed, reason) — reason explains why if blocked.
        """
        now = datetime.utcnow()

        # Reset daily counter at midnight UTC
        if now.date() > self.state.day_start.date():
            self.state.trades_today = 0
            self.state.day_start = now

        # Check: Is the proposed action actually a trade?
        if decision.proposed_action.value == "hold":
            return False, "Strategist recommends HOLD — no action needed"

        # Check: Conviction threshold
        if decision.conviction_score < self.config.conviction_threshold:
            return False, (
                f"Conviction {decision.conviction_score:.2f} below threshold "
                f"{self.config.conviction_threshold:.2f}"
            )

        # Check: Analyst agreement
        if decision.analyst_agreement < self.config.min_analyst_agreement:
            return False, (
                f"Analyst agreement {decision.analyst_agreement:.2f} below minimum "
                f"{self.config.min_analyst_agreement:.2f}"
            )

        # Check: Daily trade limit
        if self.state.trades_today >= self.config.max_trades_per_day:
            return False, (
                f"Daily trade limit reached ({self.state.trades_today}/"
                f"{self.config.max_trades_per_day})"
            )

        # Check: Cooldown period
        if self.state.last_trade_time:
            cooldown = timedelta(minutes=self.config.cooldown_minutes)
            time_since_last = now - self.state.last_trade_time
            if time_since_last < cooldown:
                remaining = cooldown - time_since_last
                return False, (
                    f"Cooldown active — {remaining.seconds // 60}m remaining"
                )

        return True, "All patience checks passed"

    def record_trade(self) -> None:
        """Record that a trade was executed."""
        self.state.trades_today += 1
        self.state.last_trade_time = datetime.utcnow()
        logger.info(
            "Trade recorded. Today: %d/%d. Cooldown: %dm",
            self.state.trades_today,
            self.config.max_trades_per_day,
            self.config.cooldown_minutes,
        )
