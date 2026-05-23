from __future__ import annotations

from .agents import EntryValidator, MacroAgent, TradeBuilder, TrendAgent
from .indicators import add_features
from .journal import Journal
from .models import BotConfig, CandidateStatus, Candle, Trade
from .paper import PaperBroker
from .risk import RiskManager, entry_price
from .sessions import in_window, should_analyze


class BotEngine:
    def __init__(self, config: BotConfig, journal: Journal):
        self.config = config
        self.journal = journal
        self.macro_agent = MacroAgent()
        self.trend_agent = TrendAgent()
        self.trade_builder = TradeBuilder()
        self.entry_validator = EntryValidator()
        self.risk = RiskManager(config)
        self.broker = PaperBroker()

    def run(self, candles: list[Candle]) -> dict[str, float | int | None]:
        bars = add_features(candles)
        active_trade: Trade | None = None
        pending = []
        candidates = []

        self.journal.begin_batch()
        try:
            for idx, bar in enumerate(bars):
                if idx < 80:
                    continue
                history = bars[max(0, idx - 120) : idx + 1]

                if active_trade is not None:
                    self.broker.mark(active_trade, bar)
                    self.journal.save_trade(active_trade)
                    if active_trade.closed_at is not None:
                        self.risk.record_trade_close(active_trade)
                        active_trade = None

                if not in_window(bar.timestamp, self.config.session_start_utc, self.config.session_end_utc):
                    if active_trade is not None:
                        self.broker.force_close(active_trade, bar)
                        self.risk.record_trade_close(active_trade)
                        self.journal.save_trade(active_trade)
                        active_trade = None
                    continue

                if should_analyze(bar.timestamp, self.config.analysis_interval_minutes):
                    macro = self.macro_agent.analyze(history)
                    trend = self.trend_agent.analyze(history, macro)
                    candidate = self.trade_builder.build(history, macro, trend, self.config)
                    candidates.append(candidate)
                    self.journal.save_candidate(candidate)
                    if candidate.status is CandidateStatus.BUILT:
                        pending.append((candidate, idx + 12))

                next_pending = []
                for candidate, expires_at in pending:
                    if idx > expires_at:
                        candidate.status = CandidateStatus.EXPIRED
                        candidate.rejection_reason = "entry zone expired"
                        self.journal.save_candidate(candidate)
                        continue

                    if active_trade is not None:
                        next_pending.append((candidate, expires_at))
                        continue

                    ok, reason = self.entry_validator.validate(candidate, bar, self.config)
                    if not ok:
                        next_pending.append((candidate, expires_at))
                        continue

                    entry = entry_price(candidate.direction, bar.close, self.config.spread_pips, self.config.slippage_pips)
                    approved, risk_reason, size_units, risk_amount = self.risk.approve(candidate, entry)
                    if not approved:
                        candidate.status = CandidateStatus.REJECTED
                        candidate.rejection_reason = risk_reason
                        self.journal.save_candidate(candidate)
                        continue

                    trade = self.broker.open_trade(
                        candidate,
                        bar,
                        size_units,
                        risk_amount,
                        self.config.spread_pips,
                        self.config.slippage_pips,
                    )
                    candidate.status = CandidateStatus.EXECUTED
                    candidate.rejection_reason = reason
                    self.journal.save_candidate(candidate)
                    self.journal.save_trade(trade)
                    self.risk.record_trade_open(trade)
                    active_trade = trade
                    break
                else:
                    pending = next_pending

                if active_trade is not None:
                    pending = next_pending

            if active_trade is not None and bars:
                self.broker.force_close(active_trade, bars[-1])
                self.risk.record_trade_close(active_trade)
                self.journal.save_trade(active_trade)

            for candidate, _expires_at in pending:
                if candidate.status is CandidateStatus.BUILT:
                    candidate.status = CandidateStatus.EXPIRED
                    candidate.rejection_reason = "dataset ended before entry decision"
                    self.journal.save_candidate(candidate)
            for candidate in candidates:
                if candidate.status is CandidateStatus.BUILT:
                    candidate.status = CandidateStatus.EXPIRED
                    candidate.rejection_reason = "dataset ended before entry decision"
                    self.journal.save_candidate(candidate)
        finally:
            self.journal.end_batch()

        return self.journal.summary()
