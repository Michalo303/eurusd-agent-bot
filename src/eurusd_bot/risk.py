from __future__ import annotations

from datetime import date

from .agents import PIP
from .models import BotConfig, Direction, SetupCandidate, Trade


class RiskManager:
    def __init__(self, config: BotConfig):
        self.config = config
        self.equity = config.starting_equity
        self.daily_pnl: dict[date, float] = {}
        self.daily_trades: dict[date, int] = {}

    def approve(self, candidate: SetupCandidate, entry: float) -> tuple[bool, str, float, float]:
        day = candidate.created_at.date()
        if self.daily_trades.get(day, 0) >= self.config.max_trades_per_day:
            return False, "max trades per day reached", 0.0, 0.0

        max_daily_loss = -self.config.starting_equity * self.config.max_daily_loss_pct / 100
        if self.daily_pnl.get(day, 0.0) <= max_daily_loss:
            return False, "max daily loss reached", 0.0, 0.0

        risk_per_unit = abs(entry - candidate.stop_loss)
        if risk_per_unit <= 0:
            return False, "invalid stop distance", 0.0, 0.0

        risk_amount = self.equity * self.config.risk_per_trade_pct / 100
        pip_value_per_unit = PIP
        size_units = risk_amount / max(risk_per_unit / pip_value_per_unit, 1e-9)
        return True, "risk approved", size_units, risk_amount

    def record_trade_open(self, trade: Trade) -> None:
        day = trade.opened_at.date()
        self.daily_trades[day] = self.daily_trades.get(day, 0) + 1

    def record_trade_close(self, trade: Trade) -> None:
        if trade.pnl is None:
            return
        day = (trade.closed_at or trade.opened_at).date()
        self.daily_pnl[day] = self.daily_pnl.get(day, 0.0) + trade.pnl
        self.equity += trade.pnl


def entry_price(direction: Direction, close: float, spread_pips: float, slippage_pips: float) -> float:
    adjustment = (spread_pips / 2 + slippage_pips) * PIP
    return close + adjustment if direction is Direction.LONG else close - adjustment

