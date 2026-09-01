from __future__ import annotations

import numpy as np
import pandas as pd

TACTICAL_CONTEXT_COLUMNS = [
    "context_return_1",
    "context_return_6",
    "context_volatility_20",
    "context_volume_ratio_20",
    "context_range_pct",
    "context_gap_pct",
    "context_trend_persistence",
    "context_hour_sin",
    "context_hour_cos",
    "context_benchmark_return_6",
    "context_relative_strength_6",
]


def build_tactical_context(bars: pd.DataFrame, benchmark_bars: pd.DataFrame | None = None) -> pd.DataFrame:
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"Tactical context is missing columns: {', '.join(sorted(missing))}")
    if not isinstance(bars.index, pd.DatetimeIndex):
        raise ValueError("Tactical context must use a DatetimeIndex")

    frame = bars.copy().sort_index()
    close = pd.to_numeric(frame["Close"], errors="coerce")
    volume = pd.to_numeric(frame["Volume"], errors="coerce")
    returns = close.pct_change()
    context = pd.DataFrame(index=frame.index)
    context["context_return_1"] = returns
    context["context_return_6"] = close.pct_change(6)
    context["context_volatility_20"] = returns.rolling(20, min_periods=10).std()
    context["context_volume_ratio_20"] = volume / volume.rolling(20, min_periods=10).mean()
    context["context_range_pct"] = (frame["High"] - frame["Low"]) / close
    context["context_gap_pct"] = frame["Open"] / close.shift(1) - 1.0
    context["context_trend_persistence"] = np.sign(returns).rolling(6, min_periods=4).mean()

    hours = pd.DatetimeIndex(frame.index).hour.to_numpy(dtype=float)
    radians = 2.0 * np.pi * hours / 24.0
    context["context_hour_sin"] = np.sin(radians)
    context["context_hour_cos"] = np.cos(radians)

    if benchmark_bars is not None and not benchmark_bars.empty:
        benchmark_close = pd.to_numeric(benchmark_bars["Close"], errors="coerce").sort_index()
        benchmark_return = benchmark_close.pct_change(6).reindex(frame.index, method="ffill")
    else:
        benchmark_return = pd.Series(0.0, index=frame.index)
    context["context_benchmark_return_6"] = benchmark_return
    context["context_relative_strength_6"] = context["context_return_6"] - benchmark_return
    return context.replace([np.inf, -np.inf], np.nan)


def enrich_with_tactical_context(
    feature_frame: pd.DataFrame,
    bars: pd.DataFrame,
    benchmark_bars: pd.DataFrame | None = None,
) -> pd.DataFrame:
    context = build_tactical_context(bars, benchmark_bars)
    aligned = context.reindex(feature_frame.index)
    enriched = feature_frame.join(aligned[TACTICAL_CONTEXT_COLUMNS])
    enriched = enriched.replace([np.inf, -np.inf], np.nan).dropna(subset=TACTICAL_CONTEXT_COLUMNS)
    if enriched.empty:
        raise ValueError("No feature rows remain after tactical context enrichment")
    return enriched
