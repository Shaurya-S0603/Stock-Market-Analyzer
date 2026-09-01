from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AdaptiveThresholds:
    buy: float
    sell: float
    multiplier: float
    reason: str


def compute_adaptive_thresholds(
    base_buy: float,
    base_sell: float,
    live_row: pd.Series,
    calibrated_probability: float,
) -> AdaptiveThresholds:
    if base_sell >= base_buy:
        raise ValueError("base_sell must be below base_buy")
    if base_buy <= 0 or base_sell >= 0:
        raise ValueError("Adaptive thresholds expect a positive buy threshold and negative sell threshold")

    volatility_ratio = float(live_row.get("regime_volatility_ratio", 1.0) or 1.0)
    volatility_ratio = float(np.clip(volatility_ratio, 0.5, 2.5))
    trending = float(np.clip(float(live_row.get("regime_trending", 0.0) or 0.0), 0.0, 1.0))
    high_volatility = float(np.clip(float(live_row.get("regime_high_volatility", 0.0) or 0.0), 0.0, 1.0))
    probability = float(np.clip(calibrated_probability, 0.0, 1.0))

    regime_multiplier = 1.0 + 0.20 * (volatility_ratio - 1.0) + 0.15 * high_volatility - 0.10 * trending
    probability_strength = abs(probability - 0.5) / 0.5
    if probability >= 0.5:
        buy_probability_multiplier = 1.0 - 0.20 * probability_strength
        sell_probability_multiplier = 1.0 + 0.10 * probability_strength
    else:
        buy_probability_multiplier = 1.0 + 0.20 * probability_strength
        sell_probability_multiplier = 1.0 - 0.10 * probability_strength

    buy = max(base_buy * regime_multiplier * buy_probability_multiplier, 0.0005)
    sell_magnitude = max(abs(base_sell) * regime_multiplier * sell_probability_multiplier, 0.0005)
    reason = (
        f"volatility ratio {volatility_ratio:.2f}; trending {trending:.0%}; "
        f"high-volatility flag {high_volatility:.0%}; calibrated profitable probability {probability:.0%}"
    )
    return AdaptiveThresholds(float(buy), float(-sell_magnitude), float(regime_multiplier), reason)
