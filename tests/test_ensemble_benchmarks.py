import numpy as np
import pandas as pd

from stockmarket.benchmarks import best_benchmark, ensemble_benchmark_models
from stockmarket.features import build_features


def _features() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=320, freq="h")
    x = np.arange(len(index), dtype=float)
    close = 100 + 0.025 * x + 2.5 * np.sin(x / 5) + 1.2 * np.sin(x / 17)
    bars = pd.DataFrame(
        {"Open": close - 0.2, "High": close + 0.8, "Low": close - 0.8, "Close": close, "Volume": 1_000_000 + x * 900},
        index=index,
    )
    frame = build_features(bars, horizon=6, round_trip_cost=0.002)
    frame["context_return_6"] = frame["Close"].pct_change(6).fillna(0.0)
    frame["regime_trending"] = (np.sin(np.arange(len(frame)) / 20) > 0).astype(float)
    frame["regime_high_volatility"] = (np.cos(np.arange(len(frame)) / 25) > 0.5).astype(float)
    return frame.dropna()


def test_extended_benchmark_ladder_contains_context_and_regime_ensembles() -> None:
    rows = ensemble_benchmark_models(_features(), splits=3, purge=6)
    names = {row["model"] for row in rows}
    assert {"ridge_core", "ridge", "ridge_momentum", "context_ensemble", "regime_ensemble"}.issubset(names)
    assert all(row["folds"] == 3 for row in rows)
    assert best_benchmark(rows)["model"] in names
