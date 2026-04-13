"""Configuration loading and validation."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ExchangeConfig(BaseModel):
    name: str = "alpaca"
    mode: str = "paper"
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USD", "ETH/USD"])
    timeframes: list[str] = Field(default_factory=lambda: ["1h", "4h", "1d"])


class CycleConfig(BaseModel):
    interval_minutes: int = 15
    market_hours_only: bool = False


class PatienceConfig(BaseModel):
    conviction_threshold: float = 0.7
    min_analyst_agreement: float = 0.5
    cooldown_minutes: int = 60
    max_trades_per_day: int = 3


class RiskConfig(BaseModel):
    max_position_size_pct: float = 5.0
    max_portfolio_risk_pct: float = 15.0
    max_drawdown_pct: float = 10.0
    max_correlated_positions: int = 2


class LLMModelConfig(BaseModel):
    model: str
    max_tokens: int = 4096


class LLMConfig(BaseModel):
    strategist: str = "claude"
    technical_analyst: str = "claude"
    sentiment_analyst: str = "grok"
    flow_analyst: str = "claude"
    risk_manager: str = "claude"
    auditor: str = "claude"
    claude: LLMModelConfig = LLMModelConfig(model="claude-sonnet-4-20250514")
    grok: LLMModelConfig = LLMModelConfig(model="grok-3")


def _get_database_url() -> str:
    """Get database URL, ensuring it uses asyncpg driver."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://tradebot:tradebot_dev@localhost:5432/tradebot",
    )
    # Railway/Neon give postgresql:// but we need postgresql+asyncpg://
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


class DatabaseConfig(BaseModel):
    url: str = _get_database_url()


class DashboardConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class Settings(BaseModel):
    exchange: ExchangeConfig = ExchangeConfig()
    cycle: CycleConfig = CycleConfig()
    patience: PatienceConfig = PatienceConfig()
    risk: RiskConfig = RiskConfig()
    llm: LLMConfig = LLMConfig()
    database: DatabaseConfig = DatabaseConfig()
    dashboard: DashboardConfig = DashboardConfig()


def _resolve_env_vars(data: dict) -> dict:
    """Replace ${VAR} placeholders with environment variable values."""
    resolved = {}
    for key, value in data.items():
        if isinstance(value, dict):
            resolved[key] = _resolve_env_vars(value)
        elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            resolved[key] = os.environ.get(env_var, value)
        else:
            resolved[key] = value
    return resolved


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Load settings from YAML file, falling back to defaults."""
    if config_path is None:
        candidates = [
            Path("config/settings.yaml"),
            Path("../config/settings.yaml"),
            Path(__file__).parent.parent.parent.parent / "config" / "settings.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = candidate
                break

    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}
        data = _resolve_env_vars(raw)
        return Settings(**data)

    return Settings()
