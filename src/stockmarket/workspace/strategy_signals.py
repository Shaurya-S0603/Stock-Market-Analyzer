"""Causal indicator rules shared by strategy backtests and future alerts."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators
from .strategy_schema import Rule, RuleGroup, Strategy


def _bool(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(bool)


def _cross(left: pd.Series, right: pd.Series | float, direction: str) -> pd.Series:
    if isinstance(right, (float, int)):
        right = pd.Series(float(right), index=left.index)
    was_valid = left.shift(1).notna() & right.shift(1).notna()
    if direction == "above":
        result = (left > right) & (left.shift(1) <= right.shift(1))
    else:
        result = (left < right) & (left.shift(1) >= right.shift(1))
    return _bool(result & was_valid)


def evaluate_rule(frame: pd.DataFrame, rule: Rule) -> pd.Series:
    close = frame["close"].astype(float)
    if rule.type in {"sma_cross", "ema_cross"}:
        maker = indicators.sma if rule.type == "sma_cross" else indicators.ema
        fast = maker(frame, rule.fast_period)
        slow = maker(frame, rule.slow_period)
        return _cross(fast, slow, rule.direction)
    if rule.type == "rsi_threshold":
        momentum = indicators.rsi(frame, rule.period)
        # Threshold comparisons are persistent states, unlike crossover events.
        return _bool((momentum > rule.threshold) if rule.direction == "above"
                     else (momentum < rule.threshold))
    if rule.type == "macd_cross":
        macd = indicators.macd(frame)
        return _cross(macd["MACD"], macd["Signal"], rule.direction)
    if rule.type in {"price_above_sma", "price_below_sma"}:
        avg = indicators.sma(frame, rule.period)
        return _bool(close > avg if rule.type == "price_above_sma" else close < avg)
    if rule.type in {"breakout_high", "breakout_low"}:
        past = indicators.breakout_levels(frame, rule.period)
        if rule.type == "breakout_high":
            return _bool(close > past["Prior high"])
        return _bool(close < past["Prior low"])
    if rule.type == "volume_above_average":
        volume = frame["volume"].astype(float)
        average = volume.shift(1).rolling(rule.period, min_periods=rule.period).mean()
        return _bool(volume > average * rule.volume_multiplier)
    raise ValueError("Unsupported strategy rule: " + rule.type)


def evaluate_group(frame: pd.DataFrame, group: RuleGroup) -> pd.Series:
    values = [evaluate_rule(frame, rule) for rule in group.rules]
    answer = values[0].copy()
    for current in values[1:]:
        answer = answer & current if group.operator == "all" else answer | current
    return _bool(answer)


def evaluate_strategy(frame: pd.DataFrame, strategy: Strategy) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError("Backtests require actual validated historical OHLCV data")
    return pd.DataFrame({
        "entry": evaluate_group(frame, strategy.entry),
        "exit": evaluate_group(frame, strategy.exit),
    }, index=frame.index)
