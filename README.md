# EURUSD Agent Bot

Research-first EURUSD trading bot scaffold inspired by a desk workflow:

1. Market data is converted into indicator context.
2. A macro agent and trend agent produce separate reads.
3. A trade builder creates candidate setups.
4. An entry validator rejects most candidates unless price/action lines up.
5. A hard risk manager outside the model decides if a trade can be placed.
6. Every candidate, rejection, decision, and paper trade is written to SQLite.

This is intentionally paper-first. Do not connect it to a live account until it has survived a long forward test with broker-realistic spread, slippage, and news handling.

## Quick Start

```powershell
python -m eurusd_bot demo --days 60
python -m eurusd_bot inspect-journal --db logs\journal.sqlite
```

Run tests:

```powershell
python -m pytest
```

## Real EURUSD Data

Download 60 days of 5m EURUSD candles from Yahoo Finance:

```powershell
python -m eurusd_bot fetch-yahoo --out data\eurusd_5m.csv
```

Or download and backtest in one command:

```powershell
python -m eurusd_bot backtest-yahoo --csv-out data\eurusd_5m.csv --db logs\journal.sqlite
```

Export the journal into spreadsheet-friendly CSV files:

```powershell
python -m eurusd_bot export-journal --db logs\journal.sqlite --out-dir logs\export
```

Run a local one-variable reflection cycle:

```powershell
python -m eurusd_bot.reflect --csv data\eurusd_5m.csv
```

Apply the best improvement when it beats the current score:

```powershell
python -m eurusd_bot.reflect --csv data\eurusd_5m.csv --apply
```

## CSV Format

Use this header for your own 5m EURUSD candles:

```csv
timestamp,open,high,low,close,volume
2026-01-02T08:00:00+00:00,1.1040,1.1048,1.1038,1.1044,1234
```

Then run:

```powershell
python -m eurusd_bot backtest --csv data\eurusd_5m.csv --db logs\journal.sqlite
```

`demo` and `backtest` reset the selected journal by default. Add `--append` when you intentionally want to keep old rows.

## Design Notes

- The current agents are deterministic heuristics so the system can be tested without API keys.
- The LLM integration point is deliberately isolated in `src/eurusd_bot/llm.py`.
- Risk limits are code-level constraints, not prompt instructions.
- Rejected setups are first-class data. They are often more useful than the small set of executed trades.

## Next Steps

- Add broker/live data adapter.
- Add economic calendar gate.
- Add OpenAI/Anthropic JSON-mode agent calls.
- Add prompt A/B testing and rejected-setup counterfactual analysis.

## Railway Paper Worker

The Docker image runs a paper-mode worker:

```powershell
python -m eurusd_bot.worker
```

It downloads recent EURUSD data, runs the current `state/strategy.yaml`, writes `state/heartbeat.json`, and exports journal CSVs.
