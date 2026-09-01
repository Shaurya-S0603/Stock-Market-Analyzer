import numpy as np
import pandas as pd

from stockmarket.features import build_features
from stockmarket.services.portfolio_backtest import run_portfolio_walk_forward


def _analysis(symbol: str, phase: float):
    from types import SimpleNamespace

    index = pd.date_range("2026-01-01", periods=360, freq="h")
    x = np.arange(len(index), dtype=float)
    close = 100 + 0.035 * x + 2.5 * np.sin(x / 8.0 + phase) + 0.7 * np.cos(x / 3.0 + phase)
    bars = pd.DataFrame(
        {"Open": close - 0.15, "High": close + 0.7, "Low": close - 0.8, "Close": close, "Volume": 1_000_000 + x * 700},
        index=index,
    )
    features = build_features(bars, horizon=6, round_trip_cost=0.0)
    return SimpleNamespace(symbol=symbol, bars=bars, training_features=features, horizon=6)


def test_portfolio_walk_forward_simulates_symbols_together() -> None:
    analyses = {"AAA": _analysis("AAA", 0.0), "BBB": _analysis("BBB", 1.2)}
    report = run_portfolio_walk_forward(
        analyses,
        {"AAA": 30.0, "BBB": 30.0},
        starting_cash=20_000,
        commission_rate=0.0,
        slippage_rate=0.0,
        buy_threshold=-1.0,
        sell_threshold=-2.0,
        max_exposure_pct=60.0,
        splits=3,
    )
    assert len(report.folds) >= 1
    assert report.total_trades >= 1
    assert all(row.train_rows >= 30 for row in report.folds)
    assert all(row.test_rows >= 8 for row in report.folds)
    assert np.isfinite(report.mean_strategy_return_pct)
    assert np.isfinite(report.mean_excess_return_pct)
    assert report.worst_drawdown_pct <= 0.0
