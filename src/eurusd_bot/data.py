from __future__ import annotations

import csv
import json
import math
import random
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Candle


def load_csv(path: str | Path) -> list[Candle]:
    candles: list[Candle] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "open", "high", "low", "close"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing columns: {', '.join(sorted(missing))}")

        for row in reader:
            candles.append(
                Candle(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume") or 0.0),
                )
            )
    return candles


def save_csv(candles: list[Candle], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for candle in candles:
            writer.writerow(
                [
                    candle.timestamp.isoformat(),
                    f"{candle.open:.6f}",
                    f"{candle.high:.6f}",
                    f"{candle.low:.6f}",
                    f"{candle.close:.6f}",
                    f"{candle.volume:.2f}",
                ]
            )


def fetch_yahoo_candles(symbol: str = "EURUSD=X", range_: str = "60d", interval: str = "5m") -> list[Candle]:
    query = urllib.parse.urlencode({"range": range_, "interval": interval})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "eurusd-agent-bot/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    chart = payload.get("chart", {})
    error = chart.get("error")
    if error:
        raise RuntimeError(f"Yahoo chart error: {error}")

    results = chart.get("result") or []
    if not results:
        raise RuntimeError("Yahoo chart returned no results")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    candles: list[Candle] = []
    for idx, timestamp in enumerate(timestamps):
        values = (
            opens[idx] if idx < len(opens) else None,
            highs[idx] if idx < len(highs) else None,
            lows[idx] if idx < len(lows) else None,
            closes[idx] if idx < len(closes) else None,
        )
        if any(value is None for value in values):
            continue
        volume = volumes[idx] if idx < len(volumes) and volumes[idx] is not None else 0.0
        candles.append(
            Candle(
                timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
                open=float(values[0]),
                high=float(values[1]),
                low=float(values[2]),
                close=float(values[3]),
                volume=float(volume),
            )
        )

    if not candles:
        raise RuntimeError("Yahoo chart returned no usable candles")
    return candles


def generate_demo_candles(days: int = 60, seed: int = 42) -> list[Candle]:
    rng = random.Random(seed)
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    price = 1.1000
    candles: list[Candle] = []
    total_steps = days * 24 * 12

    for step in range(total_steps):
        timestamp = start + timedelta(minutes=5 * step)
        if timestamp.weekday() >= 5:
            continue

        hour = timestamp.hour + timestamp.minute / 60
        session_boost = 1.8 if 7 <= hour <= 16 else 0.8
        wave = math.sin(step / 150) * 0.00003
        shock = rng.gauss(0, 0.00008 * session_boost)
        drift = 0.000006 if 12 <= hour <= 15 and math.sin(step / 600) > 0 else -0.000002
        next_close = max(0.9, price + wave + shock + drift)

        body_high = max(price, next_close)
        body_low = min(price, next_close)
        wick = abs(rng.gauss(0.00005, 0.00002)) * session_boost
        high = body_high + wick
        low = body_low - wick
        volume = max(1.0, rng.gauss(1200 * session_boost, 250))
        candles.append(Candle(timestamp, price, high, low, next_close, volume))
        price = next_close

    return candles
