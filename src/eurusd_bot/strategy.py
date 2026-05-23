from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from .models import BotConfig


DEFAULT_GOAL_PATH = Path("state/goal.yaml")
DEFAULT_STRATEGY_PATH = Path("state/strategy.yaml")


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def save_yaml(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def apply_strategy(config: BotConfig, strategy: dict[str, Any]) -> BotConfig:
    allowed = {
        "min_confluence",
        "min_rr",
        "risk_per_trade_pct",
        "max_daily_loss_pct",
        "max_trades_per_day",
        "session_start_utc",
        "session_end_utc",
    }
    values = {key: value for key, value in strategy.items() if key in allowed}
    return replace(config, **values)


def next_version(version: str) -> str:
    try:
        return f"{int(version) + 1:02d}"
    except ValueError:
        return "02"

