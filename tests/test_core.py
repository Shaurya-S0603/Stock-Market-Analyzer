import numpy as np
import pandas as pd
import pytest

from stockmarket.data import MarketDataError, normalize_ohlcv
from stockmarket.features import FEATURE_COLUMNS, build_features
from stockmarket.signals import make_signal
from stockmarket.trading import PaperPortfolio, TradingError


def bars(rows=120):
    index = pd.date_range("2025-01-01", periods=rows, freq="5min")
    close = pd.Series(100 + np.linspace(0, 8, rows) + np.sin(np.arange(rows)), index=index)
    return pd.DataFrame({"Open": close - .2, "High": close + .5, "Low": close - .5, "Close": close, "Volume": 1000}, index=index)


def test_normalize_flattens_yahoo_multiindex():
    frame = bars().rename(columns=lambda value: (value, "MSFT"))
    result = normalize_ohlcv(frame)
    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert result.index.is_monotonic_increasing


def test_empty_data_is_rejected():
    with pytest.raises(MarketDataError):
        normalize_ohlcv(pd.DataFrame())


def test_features_align_fixed_horizon_target():
    result = build_features(bars(), horizon=3)
    assert set(FEATURE_COLUMNS).issubset(result.columns)
    assert result.index[-1] < bars().index[-1]
    assert np.isfinite(result["target_return"]).all()


def test_signal_subtracts_cost_before_buying():
    assert make_signal(.01, round_trip_cost=.003).action == "Buy"
    assert make_signal(.006, round_trip_cost=.003).action == "Hold"


def test_portfolio_rejects_invalid_orders_and_tracks_pnl():
    portfolio = PaperPortfolio(1_000, commission_rate=0, slippage_rate=0)
    with pytest.raises(TradingError):
        portfolio.execute("MSFT", "buy", 20, 100)
    portfolio.execute("MSFT", "buy", 2, 100)
    with pytest.raises(TradingError):
        portfolio.execute("MSFT", "sell", 3, 120)
    portfolio.execute("MSFT", "sell", 1, 120)
    assert portfolio.summary({"MSFT": 120})["pnl"] == pytest.approx(40)
