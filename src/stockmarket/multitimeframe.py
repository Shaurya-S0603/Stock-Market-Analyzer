from __future__ import annotations

import numpy as np
import pandas as pd

from .regime import REGIME_FEATURE_COLUMNS, add_regime_features

DAILY_CONTEXT_COLUMNS = [
    "daily_return_1",
    "daily_return_5",
    "daily_volatility_20",
    "daily_trend_20",
    "daily_trend_50",
    "daily_atr_pct",
    "daily_volume_ratio_20",
]


def _naive_index(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Return timezone-naive timestamps without changing wall-clock dates."""
    if index.tz is not None:
        return index.tz_localize(None)
    return index


def build_daily_context(daily_bars: pd.DataFrame) -> pd.DataFrame:
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required.difference(daily_bars.columns)
    if missing:
        raise ValueError(f"Daily context is missing columns: {', '.join(sorted(missing))}")
    if not isinstance(daily_bars.index, pd.DatetimeIndex):
        raise ValueError("Daily context must use a DatetimeIndex")

    frame = daily_bars.copy().sort_index()
    close = pd.to_numeric(frame["Close"], errors="coerce")
    high = pd.to_numeric(frame["High"], errors="coerce")
    low = pd.to_numeric(frame["Low"], errors="coerce")
    volume = pd.to_numeric(frame["Volume"], errors="coerce")
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)

    context = pd.DataFrame(index=frame.index)
    context["daily_return_1"] = close.pct_change()
    context["daily_return_5"] = close.pct_change(5)
    context["daily_volatility_20"] = close.pct_change().rolling(20, min_periods=10).std()
    context["daily_trend_20"] = close / close.rolling(20, min_periods=10).mean() - 1.0
    context["daily_trend_50"] = close / close.rolling(50, min_periods=25).mean() - 1.0
    context["daily_atr_pct"] = true_range.rolling(14, min_periods=7).mean() / close
    context["daily_volume_ratio_20"] = volume / volume.rolling(20, min_periods=10).mean()
    context = context.replace([np.inf, -np.inf], np.nan)

    # Critical leakage guard: the row labelled date D is shifted so it contains
    # only information from the last completed daily candle (D-1 or earlier).
    return context.shift(1)


def align_daily_context(tactical_index: pd.DatetimeIndex, daily_context: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(tactical_index, pd.DatetimeIndex):
        raise ValueError("Tactical features must use a DatetimeIndex")
    if daily_context.empty:
        raise ValueError("Daily context cannot be empty")

    context = daily_context.copy()
    context.index = _naive_index(pd.DatetimeIndex(context.index)).normalize()
    context = context[~context.index.duplicated(keep="last")].sort_index()
    tactical_dates = _naive_index(pd.DatetimeIndex(tactical_index)).normalize()
    aligned = context.reindex(tactical_dates, method="ffill")
    aligned.index = tactical_index
    return aligned


def enrich_with_daily_context(feature_frame: pd.DataFrame, daily_bars: pd.DataFrame) -> pd.DataFrame:
    context = add_regime_features(build_daily_context(daily_bars))
    aligned = align_daily_context(pd.DatetimeIndex(feature_frame.index), context)
    required = DAILY_CONTEXT_COLUMNS + REGIME_FEATURE_COLUMNS
    enriched = feature_frame.join(aligned[required])
    enriched = enriched.replace([np.inf, -np.inf], np.nan).dropna(subset=required)
    if enriched.empty:
        raise ValueError("No tactical rows remain after leakage-safe daily context alignment")
    return enriched
