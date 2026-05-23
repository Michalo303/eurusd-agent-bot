from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from .data import fetch_yahoo_candles, save_csv
from .engine import BotEngine
from .journal import Journal
from .config import load_config
from .strategy import apply_strategy, load_yaml


def main() -> None:
    mode = os.getenv("HERMES_TRADING_MODE", "paper").lower()
    accept_risk = os.getenv("HERMES_TRADING_I_ACCEPT_RISK", "false").lower() == "true"
    if mode != "paper" and not accept_risk:
        raise RuntimeError("Live mode blocked. Set HERMES_TRADING_I_ACCEPT_RISK=true explicitly.")

    interval = int(os.getenv("EURUSD_WORKER_INTERVAL_SECONDS", "1800"))
    state_dir = Path(os.getenv("EURUSD_STATE_DIR", "state"))
    data_dir = Path(os.getenv("EURUSD_DATA_DIR", "data"))
    logs_dir = Path(os.getenv("EURUSD_LOGS_DIR", "logs"))
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    default_state_dir = Path(os.getenv("EURUSD_DEFAULT_STATE_DIR", "default_state"))
    seed_state(state_dir, default_state_dir)

    print("Booting eurusd paper worker", flush=True)
    failures = 0
    while True:
        try:
            summary = run_once(state_dir, data_dir, logs_dir, default_state_dir)
            failures = 0
            print(json.dumps({"event": "cycle_complete", **summary}), flush=True)
        except Exception as exc:
            failures += 1
            print(json.dumps({"event": "cycle_error", "failures": failures, "error": str(exc)}), flush=True)
            if failures >= 5:
                raise
        time.sleep(interval)


def run_once(state_dir: Path, data_dir: Path, logs_dir: Path, default_state_dir: Path | None = None) -> dict[str, object]:
    candles = fetch_yahoo_candles("EURUSD=X", "60d", "5m")
    csv_path = data_dir / "eurusd_5m.csv"
    save_csv(candles, csv_path)

    config = load_config(None)
    use_volume_strategy = os.getenv("EURUSD_USE_VOLUME_STRATEGY", "false").lower() == "true"
    default_strategy = (default_state_dir / "strategy.yaml") if default_state_dir else None
    volume_strategy = state_dir / "strategy.yaml"
    strategy_path = volume_strategy if use_volume_strategy else default_strategy
    if strategy_path is None or not strategy_path.exists():
        strategy_path = volume_strategy
    if strategy_path.exists():
        config = apply_strategy(config, load_yaml(strategy_path))

    db_path = logs_dir / "journal.sqlite"
    journal = Journal(db_path)
    journal.reset()
    summary = BotEngine(config, journal).run(candles)
    export_paths = journal.export_csvs(logs_dir / "export")
    journal.close()

    heartbeat = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "mode": os.getenv("HERMES_TRADING_MODE", "paper"),
        "candles": len(candles),
        "first_candle": candles[0].timestamp.isoformat(),
        "last_candle": candles[-1].timestamp.isoformat(),
        "summary": summary,
        "exports": export_paths,
        "strategy_source": str(strategy_path),
    }
    heartbeat_path = state_dir / "heartbeat.json"
    heartbeat_path.write_text(json.dumps(heartbeat, indent=2), encoding="utf-8")
    return heartbeat


def seed_state(state_dir: Path, default_state_dir: Path) -> None:
    if not default_state_dir.exists():
        return
    for source in default_state_dir.glob("*.yaml"):
        target = state_dir / source.name
        if not target.exists():
            shutil.copy2(source, target)


if __name__ == "__main__":
    main()
