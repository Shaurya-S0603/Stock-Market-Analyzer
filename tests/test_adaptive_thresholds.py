import pandas as pd

from stockmarket.adaptive_thresholds import compute_adaptive_thresholds


def test_adaptive_thresholds_tighten_for_strong_probability_in_normal_regime() -> None:
    row = pd.Series({"regime_volatility_ratio": 1.0, "regime_trending": 1.0, "regime_high_volatility": 0.0})
    thresholds = compute_adaptive_thresholds(0.005, -0.005, row, 0.85)
    assert 0 < thresholds.buy < 0.005
    assert thresholds.sell < 0


def test_adaptive_thresholds_demand_more_edge_in_high_volatility() -> None:
    calm = pd.Series({"regime_volatility_ratio": 0.9, "regime_trending": 0.0, "regime_high_volatility": 0.0})
    stressed = pd.Series({"regime_volatility_ratio": 2.0, "regime_trending": 0.0, "regime_high_volatility": 1.0})
    calm_thresholds = compute_adaptive_thresholds(0.005, -0.005, calm, 0.55)
    stressed_thresholds = compute_adaptive_thresholds(0.005, -0.005, stressed, 0.55)
    assert stressed_thresholds.buy > calm_thresholds.buy
    assert abs(stressed_thresholds.sell) > abs(calm_thresholds.sell)
