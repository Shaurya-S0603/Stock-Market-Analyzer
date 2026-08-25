from __future__ import annotations

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, MACD, SMAIndicator
from ta.volatility import AverageTrueRange

FEATURE_COLUMNS = [
    "sma_5", "sma_10", "rsi_7", "macd", "macd_signal", "adx", "atr",
    "volatility_10", "close_lag_1", "close_lag_2", "close_lag_3",
    "close_lag_4", "close_lag_5", "close_lag_6", "volume_chg",
]


def build_features(ohlcv: pd.DataFrame, horizon: int = 1) -> pd.DataFrame:
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    frame = ohlcv.copy()
    close = frame["Close"]
    frame["sma_5"] = SMAIndicator(close, window=5).sma_indicator()
    frame["sma_10"] = SMAIndicator(close, window=10).sma_indicator()
    frame["rsi_7"] = RSIIndicator(close, window=7).rsi()
    macd = MACD(close)
    frame["macd"] = macd.macd()
    frame["macd_signal"] = macd.macd_signal()
    frame["adx"] = ADXIndicator(frame["High"], frame["Low"], close, window=14).adx()
    frame["atr"] = AverageTrueRange(frame["High"], frame["Low"], close, window=14).average_true_range()
    frame["volatility_10"] = close.pct_change().rolling(10).std()
    frame["volume_chg"] = frame["Volume"].pct_change()
    for lag in range(1, 7):
        frame[f"close_lag_{lag}"] = close.shift(lag)
    frame["target_return"] = close.shift(-horizon) / close - 1
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLUMNS + ["target_return"])
    if frame.empty:
        raise ValueError("Not enough clean rows to build features")
    return frame
