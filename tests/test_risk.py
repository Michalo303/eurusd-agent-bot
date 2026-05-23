from datetime import datetime, timezone

from eurusd_bot.models import BotConfig, Direction, SetupCandidate
from eurusd_bot.risk import RiskManager


def test_risk_rejects_after_daily_trade_limit():
    config = BotConfig(max_trades_per_day=0)
    risk = RiskManager(config)
    candidate = SetupCandidate(
        symbol="EURUSD",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        direction=Direction.LONG,
        setup_type="test",
        confidence=7,
        confluences=["a"] * 5,
        risks=[],
        entry_low=1.1,
        entry_high=1.101,
        stop_loss=1.099,
        take_profits=[1.102, 1.103, 1.104],
        invalidation=1.098,
    )
    ok, reason, _, _ = risk.approve(candidate, 1.1005)
    assert not ok
    assert reason == "max trades per day reached"

