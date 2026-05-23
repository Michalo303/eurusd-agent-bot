from __future__ import annotations

from .models import BotConfig, Direction, FeatureBar, MacroRead, SetupCandidate, TrendRead

PIP = 0.0001


class MacroAgent:
    def analyze(self, bars: list[FeatureBar]) -> MacroRead:
        recent = bars[-60:]
        if len(recent) < 20:
            return MacroRead(Direction.FLAT, 30, ["not enough macro proxy history"])

        change = recent[-1].close - recent[0].close
        atr = recent[-1].atr14 or 0.0008
        if change > atr * 0.75:
            return MacroRead(Direction.LONG, 62, ["EURUSD 5h proxy trend rising", "risk proxy treated as supportive"])
        if change < -atr * 0.75:
            return MacroRead(Direction.SHORT, 62, ["EURUSD 5h proxy trend falling", "risk proxy treated as USD supportive"])
        return MacroRead(Direction.FLAT, 48, ["macro proxy range-bound", "prefer extremes over continuation"])


class TrendAgent:
    def analyze(self, bars: list[FeatureBar], macro: MacroRead) -> TrendRead:
        bar = bars[-1]
        factors: list[str] = []
        score = 0

        if bar.ema9 and bar.ema21 and bar.ema50:
            if bar.ema9 > bar.ema21 > bar.ema50:
                score += 2
                factors.append("EMA stack bullish")
            elif bar.ema9 < bar.ema21 < bar.ema50:
                score -= 2
                factors.append("EMA stack bearish")

        if bar.rsi14 is not None:
            if 52 <= bar.rsi14 <= 68:
                score += 1
                factors.append("RSI supports long without being extreme")
            elif 32 <= bar.rsi14 <= 48:
                score -= 1
                factors.append("RSI supports short without being extreme")

        if bar.vwap:
            if bar.close > bar.vwap:
                score += 1
                factors.append("price above VWAP")
            elif bar.close < bar.vwap:
                score -= 1
                factors.append("price below VWAP")

        if bar.macd_hist is not None:
            if bar.macd_hist > 0:
                score += 1
                factors.append("MACD histogram positive")
            elif bar.macd_hist < 0:
                score -= 1
                factors.append("MACD histogram negative")

        if macro.bias is Direction.LONG:
            score += 1
            factors.append("macro read leans long")
        elif macro.bias is Direction.SHORT:
            score -= 1
            factors.append("macro read leans short")

        direction = Direction.FLAT
        if score >= 2:
            direction = Direction.LONG
        elif score <= -2:
            direction = Direction.SHORT

        confidence = min(85, 40 + abs(score) * 8)
        regime = "trend" if abs(score) >= 3 else "range"
        key_levels = {
            "vwap": bar.vwap or bar.close,
            "session_high": bar.session_high or bar.high,
            "session_low": bar.session_low or bar.low,
        }
        if bar.prior_day_high:
            key_levels["prior_day_high"] = bar.prior_day_high
        if bar.prior_day_low:
            key_levels["prior_day_low"] = bar.prior_day_low

        invalidation = None
        if direction is Direction.LONG:
            invalidation = min(key_levels["session_low"], key_levels["vwap"])
        elif direction is Direction.SHORT:
            invalidation = max(key_levels["session_high"], key_levels["vwap"])

        return TrendRead(direction, confidence, regime, key_levels, invalidation, factors)


class TradeBuilder:
    def build(self, bars: list[FeatureBar], macro: MacroRead, trend: TrendRead, config: BotConfig) -> SetupCandidate:
        bar = bars[-1]
        atr = bar.atr14 or 0.0008
        confluences: list[str] = []
        risks: list[str] = []

        if macro.bias is trend.direction and macro.bias is not Direction.FLAT:
            confluences.append("macro and trend aligned")
        elif macro.bias is Direction.FLAT:
            confluences.append("macro flat, range play allowed")
            risks.append("macro read does not support directional follow-through")
        else:
            risks.append("macro and trend diverge")

        if trend.confidence >= 60:
            confluences.append("trend confidence >= 60")
        if macro.confidence >= 55:
            confluences.append("macro confidence >= 55")
        if bar.vwap and abs(bar.close - bar.vwap) <= atr * 0.8:
            confluences.append("price near VWAP")
        if bar.rsi14 is not None and 35 <= bar.rsi14 <= 65:
            confluences.append("RSI not extreme")
        if bar.macd_hist is not None and trend.direction is not Direction.FLAT:
            if trend.direction is Direction.LONG and bar.macd_hist > 0:
                confluences.append("MACD confirms long")
            if trend.direction is Direction.SHORT and bar.macd_hist < 0:
                confluences.append("MACD confirms short")
        if bar.prior_day_high and bar.close < bar.prior_day_high:
            confluences.append("prior-day high overhead mapped")
        if bar.prior_day_low and bar.close > bar.prior_day_low:
            confluences.append("prior-day low support mapped")

        direction = trend.direction
        setup_type = "pullback_after_vwap_reclaim"

        if macro.bias is Direction.FLAT:
            upper_distance = abs((bar.session_high or bar.high) - bar.close)
            lower_distance = abs(bar.close - (bar.session_low or bar.low))
            direction = Direction.SHORT if upper_distance < lower_distance else Direction.LONG
            setup_type = "mean_reversion_from_session_extreme"

        if direction is Direction.FLAT:
            direction = Direction.LONG if bar.close >= (bar.vwap or bar.close) else Direction.SHORT
            risks.append("trend direction flat; fallback range decision")

        if direction is Direction.LONG:
            entry_low = bar.close - atr * 0.25
            entry_high = bar.close + atr * 0.15
            stop = min(bar.low - atr * 0.35, trend.invalidation or bar.low - atr)
            risk = max(entry_high - stop, atr * 0.75)
            tps = [entry_high + risk * 1.1, entry_high + risk * 1.7, entry_high + risk * 2.5]
        else:
            entry_low = bar.close - atr * 0.15
            entry_high = bar.close + atr * 0.25
            stop = max(bar.high + atr * 0.35, trend.invalidation or bar.high + atr)
            risk = max(stop - entry_low, atr * 0.75)
            tps = [entry_low - risk * 1.1, entry_low - risk * 1.7, entry_low - risk * 2.5]

        confidence = 4.0 + min(len(confluences), 8) * 0.6
        candidate = SetupCandidate(
            symbol=config.symbol,
            created_at=bar.timestamp,
            direction=direction,
            setup_type=setup_type,
            confidence=confidence,
            confluences=confluences,
            risks=risks,
            entry_low=entry_low,
            entry_high=entry_high,
            stop_loss=stop,
            take_profits=tps,
            invalidation=trend.invalidation,
        )

        if len(confluences) < config.min_confluence:
            candidate.status = candidate.status.REJECTED
            candidate.rejection_reason = f"only {len(confluences)} confluences, need {config.min_confluence}"
        return candidate


class EntryValidator:
    def validate(self, candidate: SetupCandidate, bar: FeatureBar, config: BotConfig) -> tuple[bool, str]:
        if candidate.status.value == "rejected":
            return False, candidate.rejection_reason or "candidate already rejected"
        if not (candidate.entry_low <= bar.close <= candidate.entry_high):
            return False, "price not inside entry zone"

        spread = config.spread_pips * PIP
        if candidate.direction is Direction.LONG:
            entry = bar.close + spread / 2
            risk = entry - candidate.stop_loss
            reward = candidate.take_profits[1] - entry
        else:
            entry = bar.close - spread / 2
            risk = candidate.stop_loss - entry
            reward = entry - candidate.take_profits[1]

        if risk <= 0:
            return False, "invalid stop distance"
        if reward / risk < config.min_rr:
            return False, f"RR {reward / risk:.2f} below minimum {config.min_rr}"
        if len(candidate.confluences) < config.min_confluence:
            return False, "confluence count fell below threshold"
        return True, "entry zone touched with acceptable RR"

