from __future__ import annotations

import numpy as np
import pandas as pd

REGIME_FEATURE_COLUMNS = [
    "regime_trend_score",
    "regime_direction",
    "regime_trending",
    "regime_high_volatility",
    "regime_volatility_ratio",
    "regime_strength",
]


def add_regime_features(daily_context: pd.DataFrame) -> pd.DataFrame:
    required = {"daily_trend_20", "daily_trend_50", "daily_volatility_20"}
    missing = required.difference(daily_context.columns)
    if missing:
        raise ValueError(f"Regime detection is missing context columns: {', '.join(sorted(missing))}")

    frame = daily_context.copy()
    trend = 0.6 * frame["daily_trend_20"] + 0.4 * frame["daily_trend_50"]
    volatility = frame["daily_volatility_20"].clip(lower=0.0)
    trend_threshold = trend.abs().expanding(min_periods=15).median().clip(lower=0.004)
    volatility_median = volatility.expanding(min_periods=15).median().replace(0.0, np.nan)
    volatility_q75 = volatility.expanding(min_periods=20).quantile(0.75)

    frame["regime_trend_score"] = trend
    frame["regime_direction"] = np.sign(trend)
    frame["regime_trending"] = (trend.abs() >= trend_threshold).astype(float)
    frame["regime_high_volatility"] = (volatility >= volatility_q75).astype(float)
    frame["regime_volatility_ratio"] = volatility / volatility_median
    frame["regime_strength"] = trend.abs() / volatility.replace(0.0, np.nan)
    return frame.replace([np.inf, -np.inf], np.nan)


def regime_label(row: pd.Series) -> str:
    values = [row.get(column) for column in REGIME_FEATURE_COLUMNS]
    if any(value is None or not np.isfinite(float(value)) for value in values):
        return "unknown"
    trending = bool(float(row["regime_trending"]) >= 0.5)
    high_vol = bool(float(row["regime_high_volatility"]) >= 0.5)
    direction = float(row["regime_direction"])
    if trending and direction > 0:
        return "bullish trend · high volatility" if high_vol else "bullish trend"
    if trending and direction < 0:
        return "bearish trend · high volatility" if high_vol else "bearish trend"
    return "high-volatility range" if high_vol else "range / low trend"
