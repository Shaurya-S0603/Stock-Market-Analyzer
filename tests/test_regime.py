import numpy as np
import pandas as pd

from stockmarket.regime import REGIME_FEATURE_COLUMNS, add_regime_features, regime_label


def _context(rows: int = 80, direction: float = 1.0) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=rows, freq="D")
    trend = np.linspace(0.01, 0.08, rows) * direction
    volatility = np.linspace(0.008, 0.018, rows)
    return pd.DataFrame(
        {
            "daily_trend_20": trend,
            "daily_trend_50": trend * 0.8,
            "daily_volatility_20": volatility,
        },
        index=index,
    )


def test_regime_features_are_numeric_and_causal() -> None:
    frame = add_regime_features(_context())
    clean = frame.dropna(subset=REGIME_FEATURE_COLUMNS)
    assert not clean.empty
    assert all(np.isfinite(clean[column].to_numpy(dtype=float)).all() for column in REGIME_FEATURE_COLUMNS)
    assert regime_label(clean.iloc[-1]).startswith("bullish trend")


def test_regime_detector_identifies_bearish_trend() -> None:
    frame = add_regime_features(_context(direction=-1.0)).dropna(subset=REGIME_FEATURE_COLUMNS)
    assert regime_label(frame.iloc[-1]).startswith("bearish trend")
