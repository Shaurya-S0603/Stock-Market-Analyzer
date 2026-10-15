"""Deterministic, entirely fictional OHLCV for public connectivity tests.

These are *not* real market observations and must remain explicitly labelled.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def synthetic_demo_bars() -> pd.DataFrame:
    time = pd.bdate_range("2025-05-01", periods=320, tz="UTC")
    t = np.arange(320, dtype=float)
    close = 100 + 0.09 * t + 6 * np.sin(t / 11) + 9 * np.sin(t / 30)
    opening = np.r_[close[0], close[:-1]] + 0.35 * np.sin(t / 3)
    return pd.DataFrame({
        "open": opening,
        "close": close,
        "high": np.maximum(opening, close) + 1.2,
        "low": np.minimum(opening, close) - 1.2,
        "volume": np.rint(2000 + 400 * np.cos(t / 8)),
    }, index=time)
