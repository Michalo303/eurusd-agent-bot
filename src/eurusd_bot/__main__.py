from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .data import fetch_yahoo_candles, generate_demo_candles, load_csv, save_csv
from .engine import BotEngine
from .journal import Journal
from .strategy import apply_strategy, load_yaml


def main() -> None:
    parser = argparse.ArgumentParser(prog="eurusd_bot")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Run deterministic demo candles through the paper engine.")
    demo.add_argument("--days", type=int, default=60)
    demo.add_argument("--db", default="logs/journal.sqlite")
    demo.add_argument("--config", default=None)
    demo.add_argument("--strategy", default="state/strategy.yaml")
    demo.add_argument("--append", action="store_true", help="Append to the existing journal instead of resetting it.")

    backtest = sub.add_parser("backtest", help="Run CSV candles through the paper engine.")
    backtest.add_argument("--csv", required=True)
    backtest.add_argument("--db", default="logs/journal.sqlite")
    backtest.add_argument("--config", default=None)
    backtest.add_argument("--strategy", default="state/strategy.yaml")
    backtest.add_argument("--append", action="store_true", help="Append to the existing journal instead of resetting it.")

    fetch = sub.add_parser("fetch-yahoo", help="Download candles from Yahoo Finance chart API into CSV.")
    fetch.add_argument("--symbol", default="EURUSD=X")
    fetch.add_argument("--range", default="60d", dest="range_")
    fetch.add_argument("--interval", default="5m")
    fetch.add_argument("--out", default="data/eurusd_5m.csv")

    yahoo = sub.add_parser("backtest-yahoo", help="Download Yahoo candles and immediately run the paper engine.")
    yahoo.add_argument("--symbol", default="EURUSD=X")
    yahoo.add_argument("--range", default="60d", dest="range_")
    yahoo.add_argument("--interval", default="5m")
    yahoo.add_argument("--csv-out", default="data/eurusd_5m.csv")
    yahoo.add_argument("--db", default="logs/journal.sqlite")
    yahoo.add_argument("--config", default=None)
    yahoo.add_argument("--strategy", default="state/strategy.yaml")
    yahoo.add_argument("--append", action="store_true", help="Append to the existing journal instead of resetting it.")

    inspect = sub.add_parser("inspect-journal", help="Print journal summary.")
    inspect.add_argument("--db", default="logs/journal.sqlite")

    export = sub.add_parser("export-journal", help="Export candidates and trades tables to CSV files.")
    export.add_argument("--db", default="logs/journal.sqlite")
    export.add_argument("--out-dir", default="logs/export")

    args = parser.parse_args()

    if args.command == "inspect-journal":
        journal = Journal(args.db)
        print(json.dumps(journal.summary(), indent=2))
        journal.close()
        return

    if args.command == "export-journal":
        journal = Journal(args.db)
        print(json.dumps(journal.export_csvs(args.out_dir), indent=2))
        journal.close()
        return

    if args.command == "fetch-yahoo":
        candles = fetch_yahoo_candles(args.symbol, args.range_, args.interval)
        save_csv(candles, args.out)
        print(json.dumps({"saved": args.out, "candles": len(candles), "first": candles[0].timestamp.isoformat(), "last": candles[-1].timestamp.isoformat()}, indent=2))
        return

    config = load_config(args.config)
    if getattr(args, "strategy", None) and Path(args.strategy).exists():
        config = apply_strategy(config, load_yaml(args.strategy))
    if args.command == "demo":
        candles = generate_demo_candles(args.days)
    elif args.command == "backtest-yahoo":
        candles = fetch_yahoo_candles(args.symbol, args.range_, args.interval)
        save_csv(candles, args.csv_out)
    else:
        candles = load_csv(Path(args.csv))
    journal = Journal(args.db)
    if not args.append:
        journal.reset()
    engine = BotEngine(config, journal)
    summary = engine.run(candles)
    print(json.dumps(summary, indent=2))
    journal.close()


if __name__ == "__main__":
    main()
