from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ResearchConviction:
    """Multi-factor research view used to confirm entries and exits.

    The score is deliberately bounded to [-1, 1]. It combines model edge,
    calibrated profitable probability, price momentum, trend structure, and
    price/volume confirmation. Research priors are treated as hypotheses to
    validate, not as automatic trading rules.
    """

    score: float
    model_edge_score: float
    probability_score: float
    momentum_score: float
    trend_score: float
    volume_score: float
    positive_votes: int
    negative_votes: int
    summary: str


@dataclass(frozen=True)
class PositionLifecycle:
    symbol: str
    entry_reason: str
    bars_held: int | None
    minimum_hold_bars: int
    protected: bool


@dataclass(frozen=True)
class ResearchExitDecision:
    should_exit: bool
    reason: str
    conviction: ResearchConviction
    lifecycle: PositionLifecycle


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    if not np.isfinite(value):
        return 0.0
    return float(np.clip(value, low, high))


def _latest_row(analysis) -> dict:
    frame = getattr(analysis, "live_features", None)
    if isinstance(frame, pd.DataFrame) and not frame.empty:
        return frame.iloc[-1].to_dict()
    return {}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if np.isfinite(result) else float(default)


def compute_research_conviction(analysis) -> ResearchConviction:
    """Build a causal multi-factor conviction score from the current analysis.

    Momentum and price/volume interaction are intentionally confirmatory rather
    than standalone mandates. This keeps historical research evidence from being
    mistaken for a universal rule across markets and regimes.
    """

    latest = _latest_row(analysis)
    probability = _safe_float(getattr(analysis, "probability_profitable", 0.5), 0.5)
    net_edge = _safe_float(getattr(getattr(analysis, "signal", None), "net_edge", 0.0))
    buy_threshold = max(abs(_safe_float(getattr(analysis, "adaptive_buy_threshold", 0.003), 0.003)), 0.0005)
    sell_threshold = max(abs(_safe_float(getattr(analysis, "adaptive_sell_threshold", -0.003), -0.003)), 0.0005)
    edge_scale = max(buy_threshold, sell_threshold, 0.0005)
    model_edge_score = _clip(net_edge / (2.0 * edge_scale))
    probability_score = _clip((probability - 0.5) * 2.0)

    tactical_6 = _safe_float(latest.get("context_return_6", 0.0))
    tactical_24 = _safe_float(latest.get("context_return_24", tactical_6))
    daily_20 = _safe_float(latest.get("daily_return_20", latest.get("daily_return_5", 0.0)))
    daily_60 = _safe_float(latest.get("daily_return_60", daily_20))
    volatility = max(abs(_safe_float(latest.get("context_volatility_20", 0.01), 0.01)), 0.001)

    tactical_strength = _clip((0.60 * tactical_6 + 0.40 * tactical_24) / (3.0 * volatility))
    daily_strength = _clip((0.65 * daily_20 + 0.35 * daily_60) / max(6.0 * volatility, 0.01))
    momentum_score = _clip(0.65 * tactical_strength + 0.35 * daily_strength)

    trend_20 = _safe_float(latest.get("daily_trend_20", 0.0))
    trend_50 = _safe_float(latest.get("daily_trend_50", 0.0))
    persistence = _safe_float(latest.get("context_trend_persistence", 0.0))
    trend_scale = max(4.0 * volatility, 0.01)
    trend_score = _clip(
        0.35 * _clip(trend_20 / trend_scale)
        + 0.35 * _clip(trend_50 / trend_scale)
        + 0.30 * _clip(persistence)
    )

    volume_ratio = _safe_float(latest.get("context_volume_ratio_20", 1.0), 1.0)
    volume_shock = _safe_float(latest.get("context_volume_shock_6_20", volume_ratio - 1.0))
    price_volume = _safe_float(latest.get("context_price_volume_confirmation", 0.0))
    directional_confirmation = np.sign(momentum_score) * max(volume_ratio - 1.0, 0.0)
    volume_score = _clip(
        0.50 * _clip(price_volume)
        + 0.30 * _clip(volume_shock)
        + 0.20 * _clip(directional_confirmation)
    )

    score = _clip(
        0.30 * model_edge_score
        + 0.25 * probability_score
        + 0.25 * momentum_score
        + 0.12 * trend_score
        + 0.08 * volume_score
    )
    components = [model_edge_score, probability_score, momentum_score, trend_score, volume_score]
    positive_votes = sum(value >= 0.15 for value in components)
    negative_votes = sum(value <= -0.15 for value in components)
    summary = (
        f"research score {score:+.2f}; model {model_edge_score:+.2f}; probability {probability_score:+.2f}; "
        f"momentum {momentum_score:+.2f}; trend {trend_score:+.2f}; volume {volume_score:+.2f}; "
        f"votes +{positive_votes}/-{negative_votes}"
    )
    return ResearchConviction(
        score,
        model_edge_score,
        probability_score,
        momentum_score,
        trend_score,
        volume_score,
        int(positive_votes),
        int(negative_votes),
        summary,
    )


def _parse_order_time(raw: object) -> datetime | None:
    text = str(raw or "").replace("Z", "+00:00")
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def _latest_buy_order(symbol: str, orders: list[dict]) -> dict | None:
    candidates: list[tuple[datetime, dict]] = []
    for order in orders:
        if str(order.get("symbol", "")).upper() != symbol.upper():
            continue
        if str(order.get("side", "")).lower() != "buy":
            continue
        timestamp = _parse_order_time(order.get("created_at"))
        if timestamp is not None:
            candidates.append((timestamp, order))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _bars_since_entry(analysis, order: dict | None) -> int | None:
    if order is None:
        return None
    opened = _parse_order_time(order.get("created_at"))
    bars = getattr(analysis, "bars", None)
    if opened is None or not isinstance(bars, pd.DataFrame) or not isinstance(bars.index, pd.DatetimeIndex):
        return None
    index = pd.DatetimeIndex(bars.index)
    if index.tz is not None and opened.tzinfo is None:
        opened = opened.replace(tzinfo=index.tz)
    elif index.tz is None and opened.tzinfo is not None:
        opened = opened.replace(tzinfo=None)
    elif index.tz is not None and opened.tzinfo is not None:
        opened = opened.astimezone(index.tz)
    return int((index >= opened).sum())


def position_lifecycle(
    analysis,
    orders: list[dict],
    manual_minimum_hold_bars: int = 12,
    strategy_minimum_hold_bars: int = 3,
) -> PositionLifecycle:
    order = _latest_buy_order(str(analysis.symbol), orders)
    reason = str((order or {}).get("reason", "unknown")).lower()
    bars_held = _bars_since_entry(analysis, order)
    manual_entry = reason.startswith("manual") or "rebalance" in reason
    minimum = int(manual_minimum_hold_bars if manual_entry else strategy_minimum_hold_bars)
    protected = bars_held is not None and bars_held < minimum
    return PositionLifecycle(str(analysis.symbol).upper(), reason or "unknown", bars_held, minimum, protected)


def evaluate_research_exit(
    analysis,
    orders: list[dict],
    *,
    manual_minimum_hold_bars: int = 12,
    strategy_minimum_hold_bars: int = 3,
) -> ResearchExitDecision:
    """Confirm a model-driven exit using lifecycle and multi-factor evidence.

    Hard stops are intentionally handled by the risk-policy layer and can override
    this holding protection. This function only governs research/model exits.
    """

    conviction = compute_research_conviction(analysis)
    lifecycle = position_lifecycle(
        analysis,
        orders,
        manual_minimum_hold_bars=manual_minimum_hold_bars,
        strategy_minimum_hold_bars=strategy_minimum_hold_bars,
    )
    if lifecycle.protected:
        return ResearchExitDecision(
            False,
            f"acquisition_grace: {lifecycle.bars_held}/{lifecycle.minimum_hold_bars} bars held; {conviction.summary}",
            conviction,
            lifecycle,
        )

    signal = str(getattr(getattr(analysis, "signal", None), "action", "Hold"))
    probability = _safe_float(getattr(analysis, "probability_profitable", 0.5), 0.5)
    strong_bearish = conviction.score <= -0.22 and conviction.negative_votes >= 3
    bearish_confirmation = conviction.score <= -0.12 and conviction.negative_votes >= 2 and probability < 0.45

    if signal == "Sell" and (strong_bearish or bearish_confirmation):
        return ResearchExitDecision(
            True,
            f"confirmed_bearish_exit: {conviction.summary}",
            conviction,
            lifecycle,
        )
    return ResearchExitDecision(
        False,
        f"sell_not_confirmed: {conviction.summary}",
        conviction,
        lifecycle,
    )


def research_entry_adjustment(analysis) -> tuple[float, ResearchConviction]:
    """Return a bounded sizing multiplier for an already-eligible paper entry."""

    conviction = compute_research_conviction(analysis)
    if conviction.score <= -0.30 and conviction.negative_votes >= 3:
        return 0.0, conviction
    adjustment = float(np.clip(1.0 + 0.35 * conviction.score, 0.70, 1.25))
    return adjustment, conviction
