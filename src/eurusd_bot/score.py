from __future__ import annotations

import csv
import math
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


def load_trades_csv(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    trades: list[dict[str, Any]] = []
    for row in rows:
        trade = dict(row)
        trade["pnl"] = float(row["pnl"]) if row.get("pnl") else 0.0
        trade["risk_amount"] = float(row["risk_amount"]) if row.get("risk_amount") else 0.0
        trade["closed_at"] = datetime.fromisoformat(row["closed_at"]) if row.get("closed_at") else None
        trades.append(trade)
    return trades


def metrics(trades: list[dict[str, Any]], starting_equity: float, days: float) -> dict[str, float | int | None]:
    closed = [trade for trade in trades if trade.get("closed_at")]
    pnl = sum(float(trade["pnl"]) for trade in closed)
    return_pct = pnl / starting_equity if starting_equity else 0.0
    annual_return = return_pct * (365 / days) if days > 0 else 0.0

    equity = starting_equity
    peak = equity
    max_dd = 0.0
    returns: list[float] = []
    for trade in closed:
        trade_return = float(trade["pnl"]) / equity if equity else 0.0
        returns.append(trade_return)
        equity += float(trade["pnl"])
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)

    sharpe = None
    if len(returns) >= 2 and pstdev(returns) > 0:
        sharpe = mean(returns) / pstdev(returns) * math.sqrt(len(returns))

    wins = sum(1 for trade in closed if float(trade["pnl"]) > 0)
    losses = sum(1 for trade in closed if float(trade["pnl"]) < 0)
    gross_win = sum(float(trade["pnl"]) for trade in closed if float(trade["pnl"]) > 0)
    gross_loss = abs(sum(float(trade["pnl"]) for trade in closed if float(trade["pnl"]) < 0))
    profit_factor = gross_win / gross_loss if gross_loss else None

    return {
        "trades": len(closed),
        "wins": wins,
        "losses": losses,
        "pnl": round(pnl, 2),
        "return_pct": round(return_pct, 6),
        "annual_return": round(annual_return, 6),
        "max_drawdown": round(max_dd, 6),
        "sharpe": round(sharpe, 4) if sharpe is not None else None,
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
    }


def score(metrics_: dict[str, float | int | None], goal: dict[str, Any]) -> float:
    target = float(goal.get("target_return_annual", 0.12))
    baseline = float(goal.get("bond_baseline_annual", 0.04))
    max_dd = float(goal.get("max_drawdown", 0.06))
    min_sharpe = float(goal.get("min_sharpe", 1.0))

    annual = float(metrics_.get("annual_return") or 0.0)
    dd = float(metrics_.get("max_drawdown") or 0.0)
    sharpe = float(metrics_.get("sharpe") or 0.0)

    target_component = _clip((annual - baseline) / max(target - baseline, 0.0001), -1.0, 1.0)
    dd_component = _clip(1 - (dd / max_dd), -1.0, 1.0)
    sharpe_component = _clip(sharpe / min_sharpe, -1.0, 1.0)
    trade_count_component = _clip(float(metrics_.get("trades") or 0) / 100, 0.0, 1.0)

    composite = (
        target_component * 0.45
        + dd_component * 0.25
        + sharpe_component * 0.20
        + trade_count_component * 0.10
    )
    return round(_clip(composite, -1.0, 1.0), 4)


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))

