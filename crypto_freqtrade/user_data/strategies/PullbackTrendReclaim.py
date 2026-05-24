from __future__ import annotations

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IntParameter
from freqtrade.strategy.interface import IStrategy


class PullbackTrendReclaim(IStrategy):
    """
    Conservative BTC/ETH long-only pullback strategy.

    Intent:
    - Stop chasing late breakouts.
    - Only trade BTC/ETH spot.
    - Buy trend pullbacks after a reclaim, not fresh vertical candles.
    - Keep dry-run risk modest until forward evidence exists.
    """

    INTERFACE_VERSION = 3

    timeframe = "15m"
    startup_candle_count = 260
    process_only_new_candles = True
    can_short = False

    stoploss = -0.035
    trailing_stop = True
    trailing_stop_positive = 0.012
    trailing_stop_positive_offset = 0.028
    trailing_only_offset_is_reached = True
    minimal_roi = {
        "0": 0.035,
        "240": 0.022,
        "720": 0.012,
    }

    ema_fast_period = IntParameter(12, 34, default=21, space="buy", optimize=False)
    ema_mid_period = IntParameter(40, 80, default=55, space="buy", optimize=False)
    ema_slow_period = IntParameter(150, 240, default=200, space="buy", optimize=False)
    rsi_pullback_min = IntParameter(35, 45, default=38, space="buy", optimize=False)
    rsi_pullback_max = IntParameter(50, 60, default=55, space="buy", optimize=False)
    atr_min_pct = DecimalParameter(0.002, 0.008, default=0.003, decimals=3, space="buy", optimize=False)
    atr_max_pct = DecimalParameter(0.018, 0.060, default=0.040, decimals=3, space="buy", optimize=False)
    max_extension_atr = DecimalParameter(0.20, 1.50, default=0.85, decimals=2, space="buy", optimize=False)

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 8},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 2,
                "stop_duration_candles": 48,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 192,
                "trade_limit": 2,
                "stop_duration_candles": 96,
                "max_allowed_drawdown": 0.06,
            },
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast_period.value)
        dataframe["ema_mid"] = ta.EMA(dataframe, timeperiod=self.ema_mid_period.value)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow_period.value)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"].replace(0, np.nan)
        dataframe["volume_sma"] = dataframe["volume"].rolling(48).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_sma"].replace(0, np.nan)

        typical_price = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3
        rolling_volume = dataframe["volume"].rolling(96).sum().replace(0, np.nan)
        dataframe["vwap_proxy"] = (typical_price * dataframe["volume"]).rolling(96).sum() / rolling_volume
        dataframe["distance_mid_atr"] = (dataframe["close"] - dataframe["ema_mid"]) / dataframe["atr"].replace(0, np.nan)

        dataframe["trend_ok"] = (
            (dataframe["ema_fast"] > dataframe["ema_mid"])
            & (dataframe["ema_mid"] > dataframe["ema_slow"])
            & (dataframe["ema_slow"] > dataframe["ema_slow"].shift(12))
            & (dataframe["close"] > dataframe["ema_slow"])
        ).astype(int)

        dataframe["pullback_ok"] = (
            (dataframe["low"] <= dataframe["ema_mid"] + dataframe["atr"] * 0.35)
            & (dataframe["close"] >= dataframe["ema_fast"])
            & (dataframe["close"] >= dataframe["vwap_proxy"])
            & (dataframe["rsi"] >= self.rsi_pullback_min.value)
            & (dataframe["rsi"] <= self.rsi_pullback_max.value)
        ).astype(int)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "enter_long"] = 0
        dataframe.loc[:, "enter_tag"] = ""

        entry = (
            (dataframe["trend_ok"] == 1)
            & (dataframe["pullback_ok"] == 1)
            & dataframe["atr_pct"].between(self.atr_min_pct.value, self.atr_max_pct.value)
            & (dataframe["distance_mid_atr"] <= self.max_extension_atr.value)
            & (dataframe["volume_ratio"].fillna(0) >= 0.75)
            & (dataframe["close"] > dataframe["close"].shift(1))
        )

        dataframe.loc[entry, "enter_long"] = 1
        dataframe.loc[entry, "enter_tag"] = "trend_pullback_reclaim"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "exit_long"] = 0
        dataframe.loc[:, "exit_tag"] = ""

        take_strength = (dataframe["rsi"] > 68) & (dataframe["close"] > dataframe["ema_mid"] + dataframe["atr"] * 1.2)
        trend_failed = (dataframe["close"] < dataframe["ema_mid"]) & (dataframe["close"].shift(1) < dataframe["ema_mid"].shift(1))

        dataframe.loc[take_strength, "exit_long"] = 1
        dataframe.loc[take_strength, "exit_tag"] = "strength_take_profit"
        dataframe.loc[trend_failed, "exit_long"] = 1
        dataframe.loc[trend_failed, "exit_tag"] = "pullback_failed"
        return dataframe

