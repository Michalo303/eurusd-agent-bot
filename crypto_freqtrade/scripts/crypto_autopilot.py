#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/opt/trading/crypto-pullback")
STATE = ROOT / "user_data" / "autopilot_state.json"
HYPOTHESES = ROOT / "user_data" / "autopilot_hypotheses.jsonl"
STRATEGY = ROOT / "user_data" / "strategies" / "PullbackTrendReclaim.py"
MIN_NEW_TRADES = 10


def main() -> None:
    ROOT.joinpath("user_data").mkdir(parents=True, exist_ok=True)
    trades = load_trades()
    closed = [trade for trade in trades if not trade.get("is_open")]
    state = load_state()
    last_count = int(state.get("last_reflected_closed_count", 0))
    new_closed = closed[last_count:]

    event = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "closed_count": len(closed),
        "new_closed_count": len(new_closed),
        "action": "wait",
        "reason": "",
    }

    if len(new_closed) < MIN_NEW_TRADES:
        event["reason"] = f"need {MIN_NEW_TRADES} new closed trades before reflection"
        write_event(event)
        save_state(state | {"last_seen_closed_count": len(closed)})
        print(json.dumps(event, indent=2))
        return

    metrics = score(new_closed)
    event["metrics"] = metrics
    if metrics["pnl"] >= 0 and metrics["win_rate"] >= 0.45:
        event["reason"] = "new trade batch acceptable, no change"
        state["last_reflected_closed_count"] = len(closed)
        write_event(event)
        save_state(state)
        print(json.dumps(event, indent=2))
        return

    change = choose_change()
    if change is None:
        event["reason"] = "no safe parameter change remaining"
        state["last_reflected_closed_count"] = len(closed)
        write_event(event)
        save_state(state)
        print(json.dumps(event, indent=2))
        return

    apply_change(change)
    restart_bot()
    state["last_reflected_closed_count"] = len(closed)
    event.update(
        {
            "action": "changed_one_variable",
            "changed_variable": change["name"],
            "old_value": change["old"],
            "new_value": change["new"],
            "reason": "negative or weak new closed-trade batch",
        }
    )
    write_event(event)
    save_state(state)
    print(json.dumps(event, indent=2))


def load_trades() -> list[dict]:
    proc = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "freqtrade",
            "freqtrade",
            "show-trades",
            "--db-url",
            "sqlite:////freqtrade/user_data/tradesv3.sqlite",
            "--print-json",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(proc.stdout or "[]")


def load_state() -> dict:
    if not STATE.exists():
        return {}
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def score(trades: list[dict]) -> dict:
    pnl = sum(float(t.get("profit_abs") or t.get("realized_profit") or 0.0) for t in trades)
    wins = sum(1 for t in trades if float(t.get("profit_abs") or 0.0) > 0)
    losses = sum(1 for t in trades if float(t.get("profit_abs") or 0.0) < 0)
    return {
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "pnl": round(pnl, 4),
        "win_rate": round(wins / len(trades), 4) if trades else None,
    }


def choose_change() -> dict | None:
    text = STRATEGY.read_text(encoding="utf-8")
    candidates = [
        ("rsi_pullback_max", 55, 49, -2),
        ("max_extension_atr", 0.85, 0.55, -0.10),
        ("rsi_pullback_min", 38, 44, 2),
    ]
    for name, _start, limit, step in candidates:
        value = find_default(text, name)
        if value is None:
            continue
        new_value = round(value + step, 2)
        if step < 0 and new_value >= limit:
            return {"name": name, "old": value, "new": new_value}
        if step > 0 and new_value <= limit:
            return {"name": name, "old": value, "new": new_value}
    return None


def find_default(text: str, name: str) -> float | None:
    pattern = rf"{name}\s*=.*?default=([0-9.]+)"
    match = re.search(pattern, text, flags=re.DOTALL)
    return float(match.group(1)) if match else None


def apply_change(change: dict) -> None:
    text = STRATEGY.read_text(encoding="utf-8")
    name = change["name"]
    old = change["old"]
    new = change["new"]
    pattern = rf"({name}\s*=.*?default=){old:g}"
    updated, count = re.subn(pattern, rf"\g<1>{new:g}", text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"failed to update {name}")
    backup = STRATEGY.with_suffix(f".{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.bak")
    backup.write_text(text, encoding="utf-8")
    STRATEGY.write_text(updated, encoding="utf-8")


def restart_bot() -> None:
    subprocess.run(["docker", "compose", "restart", "freqtrade"], cwd=ROOT, check=True)


def write_event(event: dict) -> None:
    with HYPOTHESES.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


if __name__ == "__main__":
    main()
