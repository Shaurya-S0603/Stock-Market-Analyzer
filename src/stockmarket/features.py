from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "sma_5", "sma_10", "rsi_7", "macd", "macd_signal", "adx", "atr",
    "volatility_10", "close_lag_1", "close_lag_2", "close_lag_3",
    "close_lag_4", "close_lag_5", "close_lag_6", "volume_chg",
]


def _wilder_ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()


def _true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["Close"].shift(1)
    ranges = pd.concat([frame["High"]-frame["Low"],(frame["High"]-previous_close).abs(),(frame["Low"]-previous_close).abs()],axis=1)
    return ranges.max(axis=1)


def _rsi(close: pd.Series, window: int = 7) -> pd.Series:
    delta=close.diff(); gain=delta.clip(lower=0.0); loss=-delta.clip(upper=0.0)
    avg_gain=_wilder_ema(gain,window); avg_loss=_wilder_ema(loss,window)
    rs=avg_gain/avg_loss.replace(0.0,np.nan)
    result=100.0-(100.0/(1.0+rs))
    return result.where(avg_loss.ne(0.0),100.0)


def _adx(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    high=frame["High"]; low=frame["Low"]; previous_high=high.shift(1); previous_low=low.shift(1)
    up_move=high-previous_high; down_move=previous_low-low
    plus_dm=pd.Series(np.where((up_move>down_move)&(up_move>0),up_move,0.0),index=frame.index)
    minus_dm=pd.Series(np.where((down_move>up_move)&(down_move>0),down_move,0.0),index=frame.index)
    atr=_wilder_ema(_true_range(frame),window)
    plus_di=100.0*_wilder_ema(plus_dm,window)/atr.replace(0.0,np.nan)
    minus_di=100.0*_wilder_ema(minus_dm,window)/atr.replace(0.0,np.nan)
    denominator=(plus_di+minus_di).replace(0.0,np.nan)
    dx=(100.0*(plus_di-minus_di).abs()/denominator).fillna(0.0)
    return _wilder_ema(dx,window)


def build_features(ohlcv: pd.DataFrame, horizon: int = 1, include_target: bool = True) -> pd.DataFrame:
    if horizon < 1: raise ValueError("horizon must be at least 1")
    required={"Open","High","Low","Close","Volume"}; missing=required.difference(ohlcv.columns)
    if missing: raise ValueError(f"OHLCV data is missing columns: {', '.join(sorted(missing))}")
    frame=ohlcv.copy().sort_index(); close=pd.to_numeric(frame["Close"],errors="coerce")
    frame["sma_5"]=close.rolling(5,min_periods=5).mean(); frame["sma_10"]=close.rolling(10,min_periods=10).mean(); frame["rsi_7"]=_rsi(close,7)
    ema_12=close.ewm(span=12,adjust=False,min_periods=12).mean(); ema_26=close.ewm(span=26,adjust=False,min_periods=26).mean()
    frame["macd"]=ema_12-ema_26; frame["macd_signal"]=frame["macd"].ewm(span=9,adjust=False,min_periods=9).mean(); frame["adx"]=_adx(frame,14); frame["atr"]=_wilder_ema(_true_range(frame),14)
    frame["volatility_10"]=close.pct_change().rolling(10,min_periods=10).std(); frame["volume_chg"]=pd.to_numeric(frame["Volume"],errors="coerce").pct_change()
    for lag in range(1,7): frame[f"close_lag_{lag}"]=close.shift(lag)
    required_columns=list(FEATURE_COLUMNS)
    if include_target:
        frame["target_return"]=close.shift(-horizon)/close-1.0; required_columns.append("target_return")
    frame=frame.replace([np.inf,-np.inf],np.nan).dropna(subset=required_columns)
    if frame.empty: raise ValueError("Not enough clean rows to build features")
    return frame
