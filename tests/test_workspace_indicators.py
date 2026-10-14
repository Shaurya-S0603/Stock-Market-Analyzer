"""Numerical reference and causal/invariance tests for Phase 2 indicators."""
import numpy as np
import pandas as pd
import pytest

from stockmarket.workspace import indicators as ind


def bars(n=100):
    x = np.arange(n, dtype=float)
    close = 100 + x * .3 + np.sin(x / 3)
    return pd.DataFrame({
        "open": close - .1, "high": close + 1.5, "low": close - 1.5,
        "close": close, "volume": 1000 + x,
    }, index=pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC"))


def test_rolling_indicators_match_simple_independent_reference():
    frame = bars()
    close = frame["close"]
    n = 20
    assert np.isnan(ind.sma(frame, n).iloc[n-2])
    assert ind.sma(frame, n).iloc[-1] == pytest.approx(close.iloc[-n:].mean())
    weights = np.arange(1, n+1)
    assert ind.wma(frame, n).iloc[-1] == pytest.approx(
        float((close.iloc[-n:].to_numpy()*weights).sum()/weights.sum())
    )
    assert ind.ema(frame, n).iloc[-1] == pytest.approx(
        close.ewm(span=n, adjust=False, min_periods=n).mean().iloc[-1]
    )
    assert ind.roc(frame, 12).iloc[-1] == pytest.approx(
        (close.iloc[-1]/close.iloc[-13] - 1)*100
    )


def test_rsi_increasing_decreasing_and_constant_series():
    a = bars(80)
    a["close"] = np.arange(80) + 100.0
    assert ind.rsi(a).iloc[-1] == 100
    a["close"] = 200.0 - np.arange(80)
    assert ind.rsi(a).iloc[-1] == 0
    a["close"] = 100.0
    assert ind.rsi(a).iloc[-1] == 50


def test_macd_bollinger_stochastic_atr_and_breakouts():
    frame = bars()
    macd = ind.macd(frame)
    assert macd["MACD"].iloc[-1] - macd["Signal"].iloc[-1] == pytest.approx(macd["Histogram"].iloc[-1])
    bb = ind.bollinger(frame)
    assert bb["Middle"].iloc[-1] == pytest.approx(frame["close"].iloc[-20:].mean())
    assert bb["Upper"].iloc[-1] > bb["Lower"].iloc[-1]
    osc = ind.stochastic(frame)
    assert 0 <= osc["%K"].iloc[-1] <= 100
    assert ind.atr(frame).iloc[-1] >= 3
    prior = ind.breakout_levels(frame, 20)
    assert prior["Prior high"].iloc[-1] == pytest.approx(frame["high"].iloc[-21:-1].max())
    assert ind.obv(frame).iloc[0] == 0


def test_vwap_utc_day_resets_and_ignores_zero_volume():
    index = pd.to_datetime(["2026-01-01T14:00:00Z", "2026-01-01T15:00:00Z", "2026-01-02T14:00:00Z"])
    frame = pd.DataFrame({"open":[10,12,20],"high":[10,12,20],"low":[10,12,20],
                          "close":[10,12,20],"volume":[1,3,2]}, index=index)
    result = ind.vwap_utc_day(frame)
    assert result.iloc[1] == pytest.approx(11.5)
    assert result.iloc[2] == pytest.approx(20)


def test_indicators_are_causal_when_future_rows_are_added():
    full = bars(110)
    prefix = full.iloc[:85]
    for function in [ind.sma, ind.ema, ind.wma, ind.rsi, ind.atr, ind.roc,
                     ind.obv, ind.vwap_utc_day, ind.breakout_levels, ind.macd, ind.bollinger, ind.stochastic]:
        left, right = function(prefix), function(full).iloc[:85]
        (pd.testing.assert_frame_equal(left, right) if isinstance(left, pd.DataFrame)
         else pd.testing.assert_series_equal(left, right))


def test_invalid_settings_rejected():
    with pytest.raises(ValueError):
        ind.sma(bars(), 1)
    with pytest.raises(ValueError):
        ind.macd(bars(), 30, 12)
    with pytest.raises(ValueError):
        ind.bollinger(bars(), 20, 0)
