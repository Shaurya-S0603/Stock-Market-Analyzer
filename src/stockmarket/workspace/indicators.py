"""Deterministic technical indicators for the local-first research workspace.

All rolling features use current and prior observations only. A warm-up region
is NaN, never backfilled using future prices. These are research indicators,
not orders or investment recommendations.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _length(value: int) -> int:
    period = int(value)
    if period < 2 or period > 1000:
        raise ValueError("Indicator period must be between 2 and 1000")
    return period


def _series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise ValueError(f"Historical frame lacks {column}")
    return pd.to_numeric(frame[column], errors="raise").astype(float)


def sma(frame: pd.DataFrame, period: int = 20) -> pd.Series:
    return _series(frame, "close").rolling(_length(period), min_periods=_length(period)).mean().rename(f"SMA {period}")


def ema(frame: pd.DataFrame, period: int = 20) -> pd.Series:
    n = _length(period)
    return _series(frame, "close").ewm(span=n, adjust=False, min_periods=n).mean().rename(f"EMA {n}")


def wma(frame: pd.DataFrame, period: int = 20) -> pd.Series:
    n = _length(period)
    weights = np.arange(1, n + 1, dtype=float)
    return _series(frame, "close").rolling(n, min_periods=n).apply(
        lambda values: float(np.dot(values, weights) / weights.sum()), raw=True
    ).rename(f"WMA {n}")


def rsi(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    n = _length(period)
    diff = _series(frame, "close").diff()
    gain = diff.clip(lower=0)
    loss = -diff.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ratio = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - 100 / (1 + ratio)
    result = result.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    result = result.mask((avg_gain == 0) & (avg_loss > 0), 0.0)
    result = result.mask((avg_gain == 0) & (avg_loss == 0), 50.0)
    return result.rename(f"RSI {n}")


def macd(frame: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    f, s, p = _length(fast), _length(slow), _length(signal)
    if f >= s:
        raise ValueError("MACD fast period must be smaller than slow period")
    close = _series(frame, "close")
    fast_avg = close.ewm(span=f, adjust=False, min_periods=f).mean()
    slow_avg = close.ewm(span=s, adjust=False, min_periods=s).mean()
    line = fast_avg - slow_avg
    signal_line = line.ewm(span=p, adjust=False, min_periods=p).mean()
    return pd.DataFrame({"MACD": line, "Signal": signal_line, "Histogram": line - signal_line}, index=frame.index)


def bollinger(frame: pd.DataFrame, period: int = 20, stddev: float = 2.0) -> pd.DataFrame:
    n = _length(period)
    if not 0 < float(stddev) <= 10:
        raise ValueError("Bollinger deviation must be between 0 and 10")
    close = _series(frame, "close")
    mid = close.rolling(n, min_periods=n).mean()
    std = close.rolling(n, min_periods=n).std(ddof=0)
    return pd.DataFrame({"Lower": mid - float(stddev) * std, "Middle": mid,
                         "Upper": mid + float(stddev) * std}, index=frame.index)


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    n = _length(period)
    high, low, close = (_series(frame, col) for col in ("high", "low", "close"))
    previous = close.shift()
    true_range = pd.concat([(high - low), (high - previous).abs(),
                            (low - previous).abs()], axis=1).max(axis=1)
    return true_range.rolling(n, min_periods=n).mean().rename(f"ATR {n}")


def roc(frame: pd.DataFrame, period: int = 12) -> pd.Series:
    n = _length(period)
    return (_series(frame, "close").pct_change(periods=n, fill_method=None) * 100).rename(f"ROC {n}")


def stochastic(frame: pd.DataFrame, period: int = 14, smooth: int = 3) -> pd.DataFrame:
    n, k = _length(period), _length(smooth)
    high = _series(frame, "high").rolling(n, min_periods=n).max()
    low = _series(frame, "low").rolling(n, min_periods=n).min()
    percent_k = (100 * (_series(frame, "close") - low) / (high - low).replace(0, np.nan)).clip(0, 100)
    return pd.DataFrame({"%K": percent_k, "%D": percent_k.rolling(k, min_periods=k).mean()}, index=frame.index)


def obv(frame: pd.DataFrame) -> pd.Series:
    movement = np.sign(_series(frame, "close").diff().fillna(0))
    return (movement * _series(frame, "volume")).cumsum().rename("OBV")


def vwap_utc_day(frame: pd.DataFrame) -> pd.Series:
    """UTC-date segmented VWAP, not an exchange-calendar session VWAP."""
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ValueError("VWAP requires timezone-aware intraday observations")
    typical = (_series(frame, "high") + _series(frame, "low") + _series(frame, "close")) / 3.0
    volume = _series(frame, "volume")
    group = frame.index.tz_convert("UTC").normalize()
    num = (typical * volume).groupby(group).cumsum()
    den = volume.groupby(group).cumsum()
    return (num / den.replace(0, np.nan)).rename("VWAP (UTC date)")


def breakout_levels(frame: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    n = _length(period)
    return pd.DataFrame({
        "Prior high": _series(frame, "high").shift(1).rolling(n, min_periods=n).max(),
        "Prior low": _series(frame, "low").shift(1).rolling(n, min_periods=n).min(),
    }, index=frame.index)


def indicator_snapshot(frame: pd.DataFrame, *, sma_period: int = 20, rsi_period: int = 14) -> dict:
    if frame.empty:
        return {"close": None, "sma": None, "rsi": None, "volume": None}
    avg, momentum = sma(frame, sma_period), rsi(frame, rsi_period)
    def recent(series):
        value = series.iloc[-1]
        return float(value) if pd.notna(value) and np.isfinite(value) else None
    return {
        "close": recent(_series(frame, "close")),
        "sma": recent(avg),
        "rsi": recent(momentum),
        "volume": recent(_series(frame, "volume")),
    }
