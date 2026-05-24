from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_config
from .data import load_csv
from .engine import BotEngine
from .journal import Journal
from .score import metrics, score
from .strategy import DEFAULT_GOAL_PATH, DEFAULT_STRATEGY_PATH, apply_strategy, load_yaml, next_version, save_yaml


def main() -> None:
    parser = argparse.ArgumentParser(prog="eurusd_bot.reflect")
    parser.add_argument("--csv", default="data/eurusd_5m.csv")
    parser.add_argument("--goal", default=str(DEFAULT_GOAL_PATH))
    parser.add_argument("--strategy", default=str(DEFAULT_STRATEGY_PATH))
    parser.add_argument("--config", default=None)
    parser.add_argument("--history-dir", default="state/history")
    parser.add_argument("--hypotheses", default="state/hypotheses.jsonl")
    parser.add_argument("--apply", action="store_true", help="Write the best one-variable change into strategy.yaml.")
    parser.add_argument("--min-improvement", type=float, default=0.001, help="Minimum score lift required before applying.")
    args = parser.parse_args()

    result = reflect_once(args)
    print(json.dumps(result, indent=2))


def reflect_once(args: argparse.Namespace) -> dict[str, Any]:
    goal = load_yaml(args.goal)
    strategy = load_yaml(args.strategy)
    base = _evaluate(args.csv, args.config, strategy)
    candidates = []
    for variant in _variants(strategy, base, goal):
        evaluated = _evaluate(args.csv, args.config, variant)
        changed = _changed_variable(strategy, variant)
        evaluated["changed_variable"] = changed
        evaluated["old_value"] = strategy.get(changed) if changed else None
        evaluated["new_value"] = variant.get(changed) if changed else None
        candidates.append(evaluated)
    best = max(candidates, key=lambda item: item["score"]) if candidates else base

    improvement = best["score"] - base["score"]
    should_apply = bool(args.apply and improvement >= args.min_improvement)

    hypothesis = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_score": base["score"],
        "best_score": best["score"],
        "improvement": round(improvement, 6),
        "min_improvement": args.min_improvement,
        "base_metrics": base["metrics"],
        "best_metrics": best["metrics"],
        "changed_variable": best["changed_variable"],
        "old_value": best["old_value"],
        "new_value": best["new_value"],
        "applied": should_apply,
    }

    if hypothesis["applied"]:
        _save_strategy_change(args.strategy, args.history_dir, strategy, best["strategy"])
        _append_jsonl(args.hypotheses, hypothesis)
    return hypothesis


def _evaluate(csv_path: str, config_path: str | None, strategy: dict[str, Any]) -> dict[str, Any]:
    candles = load_csv(csv_path)
    config = apply_strategy(load_config(config_path), strategy)
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "journal.sqlite"
        journal = Journal(db)
        journal.reset()
        summary = BotEngine(config, journal).run(candles)
        journal.conn.commit()
        trades = _load_trades_from_db(db)
        journal.close()

    days = (candles[-1].timestamp - candles[0].timestamp).total_seconds() / 86400
    metric = metrics(trades, config.starting_equity, days)
    goal = load_yaml(DEFAULT_GOAL_PATH) if DEFAULT_GOAL_PATH.exists() else {}
    return {
        "strategy": strategy,
        "summary": summary,
        "metrics": metric,
        "score": score(metric, goal),
        "changed_variable": None,
        "old_value": None,
        "new_value": None,
    }


def _load_trades_from_db(db: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    trades = []
    for row in conn.execute("select * from trades where pnl is not null order by closed_at"):
        item = dict(row)
        item["closed_at"] = datetime.fromisoformat(item["closed_at"]) if item.get("closed_at") else None
        trades.append(item)
    conn.close()
    return trades


def _variants(strategy: dict[str, Any], base: dict[str, Any], goal: dict[str, Any]) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    annual = float(base["metrics"].get("annual_return") or 0.0)
    drawdown = float(base["metrics"].get("max_drawdown") or 0.0)
    target = float(goal.get("target_return_annual", 0.12))
    max_dd = float(goal.get("max_drawdown", 0.06))

    if annual < target:
        variants.extend(
            [
                _change(strategy, "min_confluence", max(3, int(strategy.get("min_confluence", 5)) - 1)),
                _change(strategy, "min_rr", max(1.1, round(float(strategy.get("min_rr", 1.5)) - 0.1, 2))),
                _change(strategy, "max_trades_per_day", min(5, int(strategy.get("max_trades_per_day", 2)) + 1)),
            ]
        )
    if drawdown > max_dd * 0.7:
        variants.extend(
            [
                _change(strategy, "min_confluence", min(8, int(strategy.get("min_confluence", 5)) + 1)),
                _change(strategy, "min_rr", min(3.0, round(float(strategy.get("min_rr", 1.5)) + 0.1, 2))),
                _change(strategy, "risk_per_trade_pct", max(0.05, round(float(strategy.get("risk_per_trade_pct", 0.25)) - 0.05, 2))),
            ]
        )

    unique: dict[str, dict[str, Any]] = {}
    for variant in variants:
        changed = _changed_variable(strategy, variant)
        if changed:
            unique[f"{changed}:{variant[changed]}"] = variant
    return list(unique.values())


def _change(strategy: dict[str, Any], key: str, value: Any) -> dict[str, Any]:
    variant = deepcopy(strategy)
    variant[key] = value
    return variant


def _changed_variable(old: dict[str, Any], new: dict[str, Any]) -> str | None:
    changes = [key for key in sorted(set(old) | set(new)) if old.get(key) != new.get(key)]
    return changes[0] if len(changes) == 1 else None


def _save_strategy_change(path: str, history_dir: str, old: dict[str, Any], new: dict[str, Any]) -> None:
    current = Path(path)
    history = Path(history_dir)
    history.mkdir(parents=True, exist_ok=True)
    version = str(old.get("version", "01"))
    shutil.copy2(current, history / f"v{version}.yaml")
    updated = deepcopy(new)
    updated["version"] = next_version(version)
    save_yaml(current, updated)


def _append_jsonl(path: str, item: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, default=str) + "\n")


if __name__ == "__main__":
    main()
