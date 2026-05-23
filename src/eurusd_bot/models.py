from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class CandidateStatus(str, Enum):
    BUILT = "built"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class FeatureBar(Candle):
    ema9: float | None = None
    ema21: float | None = None
    ema50: float | None = None
    rsi14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    atr14: float | None = None
    vwap: float | None = None
    session_high: float | None = None
    session_low: float | None = None
    prior_day_high: float | None = None
    prior_day_low: float | None = None


@dataclass
class MacroRead:
    bias: Direction
    confidence: int
    factors: list[str]


@dataclass
class TrendRead:
    direction: Direction
    confidence: int
    regime: str
    key_levels: dict[str, float]
    invalidation: float | None
    factors: list[str]


@dataclass
class SetupCandidate:
    symbol: str
    created_at: datetime
    direction: Direction
    setup_type: str
    confidence: float
    confluences: list[str]
    risks: list[str]
    entry_low: float
    entry_high: float
    stop_loss: float
    take_profits: list[float]
    invalidation: float | None
    status: CandidateStatus = CandidateStatus.BUILT
    rejection_reason: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def entry_mid(self) -> float:
        return (self.entry_low + self.entry_high) / 2


@dataclass
class EntryDecision:
    should_enter: bool
    reason: str
    score: int
    observed_price: float


@dataclass
class Trade:
    candidate_id: str
    symbol: str
    direction: Direction
    opened_at: datetime
    entry: float
    stop_loss: float
    take_profits: list[float]
    size_units: float
    risk_amount: float
    closed_at: datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    pnl: float | None = None


@dataclass
class BotConfig:
    symbol: str = "EURUSD"
    starting_equity: float = 10_000.0
    risk_per_trade_pct: float = 0.25
    max_daily_loss_pct: float = 1.0
    max_trades_per_day: int = 2
    min_confluence: int = 5
    min_rr: float = 1.5
    spread_pips: float = 0.8
    slippage_pips: float = 0.2
    analysis_interval_minutes: int = 30
    session_start_utc: str = "13:30"
    session_end_utc: str = "16:00"

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "BotConfig":
        fields = cls.__dataclass_fields__
        return cls(**{key: value for key, value in data.items() if key in fields})

