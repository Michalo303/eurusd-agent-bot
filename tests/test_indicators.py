from datetime import datetime, timedelta, timezone

from eurusd_bot.indicators import add_features, ema, rsi
from eurusd_bot.models import Candle


def test_ema_waits_for_period_then_updates():
    values = [1, 2, 3, 4, 5]
    result = ema(values, 3)
    assert result[:2] == [None, None]
    assert result[2] == 2
    assert result[-1] > result[-2]


def test_rsi_bounds():
    values = [1 + i * 0.01 for i in range(30)]
    result = rsi(values, 14)
    assert result[-1] == 100


def test_add_features_adds_prior_day_levels():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = []
    for idx in range(48):
        timestamp = start + timedelta(hours=idx)
        candles.append(Candle(timestamp, 1.0, 1.1, 0.9, 1.0, 100))

    features = add_features(candles)
    second_day = [bar for bar in features if bar.timestamp.date().isoformat() == "2026-01-02"]
    assert second_day[0].prior_day_high == 1.1
    assert second_day[0].prior_day_low == 0.9

