import numpy as np
import pandas as pd

from stockmarket.features import build_features
from stockmarket.targets import TARGET_COLUMNS, build_forward_targets


def _close() -> pd.Series:
    index = pd.date_range("2026-01-01", periods=12, freq="h")
    return pd.Series([100, 101, 100.5, 102, 104, 103, 105, 106, 104, 108, 109, 110], index=index, dtype=float)


def test_forward_targets_include_cost_adjusted_labels() -> None:
    close = _close()
    targets = build_forward_targets(close, horizon=2, round_trip_cost=0.01)
    first_return = close.iloc[2] / close.iloc[0] - 1.0
    assert targets.iloc[0]["target_return"] == first_return
    assert targets.iloc[0]["target_net_return_long"] == first_return - 0.01
    assert targets.iloc[0]["target_profitable_long"] == float(first_return > 0.01)
    assert targets.iloc[0]["target_action"] in {-1.0, 0.0, 1.0}


def test_feature_builder_exposes_richer_targets_without_leaking_into_live_frame() -> None:
    index = pd.date_range("2026-01-01", periods=160, freq="h")
    close = 100 + np.linspace(0, 20, len(index)) + np.sin(np.arange(len(index)) / 3)
    bars = pd.DataFrame(
        {"Open": close - 0.2, "High": close + 0.8, "Low": close - 0.9, "Close": close, "Volume": 1_000_000},
        index=index,
    )
    training = build_features(bars, horizon=6, include_target=True, round_trip_cost=0.003)
    live = build_features(bars, horizon=6, include_target=False, round_trip_cost=0.003)
    assert set(TARGET_COLUMNS).issubset(training.columns)
    assert not set(TARGET_COLUMNS).intersection(live.columns)
    assert live.index.max() > training.index.max()
