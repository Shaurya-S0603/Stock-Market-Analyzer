from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass(frozen=True)
class AdaptiveExitDecision:
    symbol: str
    should_exit: bool
    reason: str
    stop_price: float
    target_price: float
    trailing_stop: float
    holding_bars: int | None
    probability_profitable: float


def _latest_buy_time(symbol: str, orders: list[dict]) -> datetime | None:
    candidates: list[datetime] = []
    for order in orders:
        if str(order.get("symbol", "")).upper() != symbol.upper() or str(order.get("side", "")).lower() != "buy":
            continue
        raw = str(order.get("created_at", "")).replace("Z", "+00:00")
        try:
            candidates.append(datetime.fromisoformat(raw))
        except ValueError:
            continue
    return max(candidates) if candidates else None


def _holding_bars(analysis, orders: list[dict]) -> int | None:
    opened = _latest_buy_time(analysis.symbol, orders)
    if opened is None or not isinstance(analysis.bars.index, pd.DatetimeIndex):
        return None
    index = pd.DatetimeIndex(analysis.bars.index)
    if index.tz is not None and opened.tzinfo is None:
        opened = opened.replace(tzinfo=index.tz)
    elif index.tz is None and opened.tzinfo is not None:
        opened = opened.replace(tzinfo=None)
    return int((index >= opened).sum())


def evaluate_adaptive_exit(analysis, position, orders: list[dict], policy) -> AdaptiveExitDecision:
    if position.quantity <= 0 or position.average_cost <= 0:
        return AdaptiveExitDecision(analysis.symbol, False, "no_open_position", 0.0, 0.0, 0.0, None, 0.5)

    mark = float(analysis.price)
    latest = analysis.live_features.iloc[-1]
    atr = abs(float(latest.get("atr", 0.0) or 0.0))
    atr_pct = atr / mark * 100.0 if mark > 0 else 0.0
    stop_pct = max(float(policy.stop_loss_pct), atr_pct * float(policy.atr_stop_multiple))
    target_pct = max(float(policy.take_profit_pct), stop_pct * float(policy.reward_to_risk))
    stop_price = position.average_cost * (1.0 - stop_pct / 100.0)
    target_price = position.average_cost * (1.0 + target_pct / 100.0)

    lookback = max(int(policy.trailing_lookback_bars), 2)
    recent_high = float(pd.to_numeric(analysis.bars["High"], errors="coerce").tail(lookback).max())
    trailing_stop = recent_high * (1.0 - stop_pct / 100.0)
    effective_stop = max(stop_price, trailing_stop if recent_high > position.average_cost else stop_price)
    probability = float(getattr(analysis, "probability_profitable", 0.5))
    bars_held = _holding_bars(analysis, orders)

    reason = "hold"
    should_exit = False
    if str(analysis.signal.action) == "Sell":
        should_exit, reason = True, "signal_reversal"
    elif probability < float(policy.min_hold_probability):
        should_exit, reason = True, "confidence_decay"
    elif mark <= effective_stop:
        should_exit, reason = True, "adaptive_stop"
    elif mark >= target_price:
        should_exit, reason = True, "adaptive_take_profit"
    elif bars_held is not None and bars_held >= int(policy.max_holding_bars):
        should_exit, reason = True, "time_stop"

    return AdaptiveExitDecision(
        analysis.symbol,
        should_exit,
        reason,
        float(effective_stop),
        float(target_price),
        float(trailing_stop),
        bars_held,
        probability,
    )
