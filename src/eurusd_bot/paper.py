from __future__ import annotations

from .models import Direction, FeatureBar, SetupCandidate, Trade
from .risk import entry_price


class PaperBroker:
    def open_trade(self, candidate: SetupCandidate, bar: FeatureBar, size_units: float, risk_amount: float, spread_pips: float, slippage_pips: float) -> Trade:
        entry = entry_price(candidate.direction, bar.close, spread_pips, slippage_pips)
        return Trade(
            candidate_id=candidate.id,
            symbol=candidate.symbol,
            direction=candidate.direction,
            opened_at=bar.timestamp,
            entry=entry,
            stop_loss=candidate.stop_loss,
            take_profits=candidate.take_profits,
            size_units=size_units,
            risk_amount=risk_amount,
        )

    def mark(self, trade: Trade, bar: FeatureBar) -> Trade:
        if trade.closed_at is not None:
            return trade

        if trade.direction is Direction.LONG:
            if bar.low <= trade.stop_loss:
                self._close(trade, bar, trade.stop_loss, "stop_loss")
            elif bar.high >= trade.take_profits[-1]:
                self._close(trade, bar, trade.take_profits[-1], "tp3")
            elif bar.high >= trade.take_profits[1]:
                self._close(trade, bar, trade.take_profits[1], "tp2")
        else:
            if bar.high >= trade.stop_loss:
                self._close(trade, bar, trade.stop_loss, "stop_loss")
            elif bar.low <= trade.take_profits[-1]:
                self._close(trade, bar, trade.take_profits[-1], "tp3")
            elif bar.low <= trade.take_profits[1]:
                self._close(trade, bar, trade.take_profits[1], "tp2")
        return trade

    def force_close(self, trade: Trade, bar: FeatureBar) -> Trade:
        if trade.closed_at is None:
            self._close(trade, bar, bar.close, "session_close")
        return trade

    def _close(self, trade: Trade, bar: FeatureBar, price: float, reason: str) -> None:
        trade.closed_at = bar.timestamp
        trade.exit_price = price
        trade.exit_reason = reason
        direction_mult = 1 if trade.direction is Direction.LONG else -1
        price_pnl = (price - trade.entry) * direction_mult
        risk_per_unit = abs(trade.entry - trade.stop_loss)
        r_multiple = price_pnl / risk_per_unit if risk_per_unit else 0.0
        trade.pnl = r_multiple * trade.risk_amount

