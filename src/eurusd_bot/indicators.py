from __future__ import annotations

from collections import defaultdict

from .models import Candle, FeatureBar


def ema(values: list[float], period: int) -> list[float | None]:
    if not values:
        return []
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    alpha = 2 / (period + 1)
    current = sum(values[:period]) / period
    out[period - 1] = current
    for idx in range(period, len(values)):
        current = values[idx] * alpha + current * (1 - alpha)
        out[idx] = current
    return out


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for idx in range(1, period + 1):
        change = values[idx] - values[idx - 1]
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    out[period] = _rsi_value(avg_gain, avg_loss)

    for idx in range(period + 1, len(values)):
        change = values[idx] - values[idx - 1]
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[idx] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(candles: list[Candle], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(candles)
    if len(candles) <= period:
        return out
    trs: list[float] = []
    for idx, candle in enumerate(candles):
        if idx == 0:
            tr = candle.high - candle.low
        else:
            prev_close = candles[idx - 1].close
            tr = max(candle.high - candle.low, abs(candle.high - prev_close), abs(candle.low - prev_close))
        trs.append(tr)
    current = sum(trs[1 : period + 1]) / period
    out[period] = current
    for idx in range(period + 1, len(candles)):
        current = (current * (period - 1) + trs[idx]) / period
        out[idx] = current
    return out


def macd(values: list[float]) -> tuple[list[float | None], list[float | None], list[float | None]]:
    ema12 = ema(values, 12)
    ema26 = ema(values, 26)
    line: list[float | None] = []
    compact: list[float] = []
    compact_indexes: list[int] = []
    for idx, (fast, slow) in enumerate(zip(ema12, ema26, strict=True)):
        if fast is None or slow is None:
            line.append(None)
        else:
            value = fast - slow
            line.append(value)
            compact.append(value)
            compact_indexes.append(idx)

    signal_compact = ema(compact, 9)
    signal: list[float | None] = [None] * len(values)
    hist: list[float | None] = [None] * len(values)
    for compact_idx, original_idx in enumerate(compact_indexes):
        sig = signal_compact[compact_idx]
        signal[original_idx] = sig
        if sig is not None and line[original_idx] is not None:
            hist[original_idx] = line[original_idx] - sig
    return line, signal, hist


def add_features(candles: list[Candle]) -> list[FeatureBar]:
    closes = [c.close for c in candles]
    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)
    rsi14 = rsi(closes, 14)
    atr14 = atr(candles, 14)
    macd_line, macd_signal, macd_hist = macd(closes)
    vwap = _session_vwap(candles)
    highs, lows = _session_extremes(candles)
    prior_highs, prior_lows = _prior_day_levels(candles)

    return [
        FeatureBar(
            timestamp=candle.timestamp,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            ema9=ema9[idx],
            ema21=ema21[idx],
            ema50=ema50[idx],
            rsi14=rsi14[idx],
            macd=macd_line[idx],
            macd_signal=macd_signal[idx],
            macd_hist=macd_hist[idx],
            atr14=atr14[idx],
            vwap=vwap[idx],
            session_high=highs[idx],
            session_low=lows[idx],
            prior_day_high=prior_highs[idx],
            prior_day_low=prior_lows[idx],
        )
        for idx, candle in enumerate(candles)
    ]


def _session_vwap(candles: list[Candle]) -> list[float | None]:
    pv_by_day: dict[object, float] = defaultdict(float)
    vol_by_day: dict[object, float] = defaultdict(float)
    out: list[float | None] = []
    for candle in candles:
        key = candle.timestamp.date()
        typical = (candle.high + candle.low + candle.close) / 3
        volume = max(candle.volume, 1.0)
        pv_by_day[key] += typical * volume
        vol_by_day[key] += volume
        out.append(pv_by_day[key] / vol_by_day[key] if vol_by_day[key] else None)
    return out


def _session_extremes(candles: list[Candle]) -> tuple[list[float | None], list[float | None]]:
    high_by_day: dict[object, float] = {}
    low_by_day: dict[object, float] = {}
    highs: list[float | None] = []
    lows: list[float | None] = []
    for candle in candles:
        key = candle.timestamp.date()
        high_by_day[key] = max(high_by_day.get(key, candle.high), candle.high)
        low_by_day[key] = min(low_by_day.get(key, candle.low), candle.low)
        highs.append(high_by_day[key])
        lows.append(low_by_day[key])
    return highs, lows


def _prior_day_levels(candles: list[Candle]) -> tuple[list[float | None], list[float | None]]:
    by_day: dict[object, list[Candle]] = defaultdict(list)
    for candle in candles:
        by_day[candle.timestamp.date()].append(candle)

    days = sorted(by_day)
    prior_levels: dict[object, tuple[float | None, float | None]] = {}
    previous: object | None = None
    for day in days:
        if previous is None:
            prior_levels[day] = (None, None)
        else:
            prior_candles = by_day[previous]
            prior_levels[day] = (max(c.high for c in prior_candles), min(c.low for c in prior_candles))
        previous = day

    highs = [prior_levels[c.timestamp.date()][0] for c in candles]
    lows = [prior_levels[c.timestamp.date()][1] for c in candles]
    return highs, lows

