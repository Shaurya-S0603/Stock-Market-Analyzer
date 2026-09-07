from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .research_intelligence import evaluate_research_exit, position_lifecycle


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
    research_score: float = 0.0
    protected: bool = False


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

    lifecycle = position_lifecycle(
        analysis,
        orders,
        manual_minimum_hold_bars=int(policy.manual_minimum_hold_bars),
        strategy_minimum_hold_bars=int(policy.strategy_minimum_hold_bars),
    )
    # A trailing high formed before a manual allocation must not immediately
    # liquidate the new position. During acquisition grace only the cost-based
    # hard stop is active; after grace the trailing stop may tighten protection.
    effective_stop = stop_price if lifecycle.protected else max(
        stop_price,
        trailing_stop if recent_high > position.average_cost else stop_price,
    )
    probability = float(getattr(analysis, "probability_profitable", 0.5))
    research_exit = evaluate_research_exit(
        analysis,
        orders,
        manual_minimum_hold_bars=int(policy.manual_minimum_hold_bars),
        strategy_minimum_hold_bars=int(policy.strategy_minimum_hold_bars),
    )
    conviction = research_exit.conviction

    # Capital protection is allowed to override the holding window. Model labels,
    # confidence decay, take-profit, and time exits are not.
    if mark <= effective_stop:
        reason = "adaptive_stop"
        should_exit = True
    elif lifecycle.protected:
        reason = "acquisition_grace"
        should_exit = False
    elif str(analysis.signal.action) == "Sell":
        should_exit = bool(research_exit.should_exit)
        reason = "research_bearish_reversal" if should_exit else "sell_not_confirmed"
    elif (
        probability < float(policy.min_hold_probability)
        and conviction.score <= -0.12
        and conviction.negative_votes >= 2
    ):
        should_exit, reason = True, "confidence_decay_confirmed"
    elif mark >= target_price:
        should_exit, reason = True, "adaptive_take_profit"
    elif (
        lifecycle.bars_held is not None
        and lifecycle.bars_held >= int(policy.max_holding_bars)
        and conviction.score <= 0.0
    ):
        should_exit, reason = True, "time_stop"
    else:
        should_exit, reason = False, "hold"

    return AdaptiveExitDecision(
        analysis.symbol,
        should_exit,
        reason,
        float(effective_stop),
        float(target_price),
        float(trailing_stop),
        lifecycle.bars_held,
        probability,
        float(conviction.score),
        bool(lifecycle.protected),
    )
