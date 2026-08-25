from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd
import yfinance as yf


REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Volume")
INTRADAY_PERIOD_LIMITS = {
    "5m": "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "730d",
    "1h": "730d",
}


class MarketDataError(RuntimeError):
    """Raised when market data cannot be safely used."""


def normalize_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    if data is None or data.empty:
        raise MarketDataError("No market data was returned")
    frame = data.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.loc[:, ~frame.columns.duplicated()]
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise MarketDataError(f"Market data is missing columns: {', '.join(missing)}")
    frame = frame.loc[:, REQUIRED_COLUMNS].sort_index()
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise MarketDataError("Market data must use a DatetimeIndex")
    for column in REQUIRED_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.replace([float("inf"), float("-inf")], pd.NA).dropna()
    frame = frame[(frame["High"] >= frame["Low"]) & (frame["Close"] > 0) & (frame["Volume"] >= 0)]
    if frame.empty:
        raise MarketDataError("Market data contains no valid OHLCV rows")
    return frame


@dataclass
class YahooFinanceProvider:
    downloader: Callable = yf.download

    def fetch(self, symbol: str, period: str = "60d", interval: str = "5m", minimum_rows: int = 80) -> pd.DataFrame:
        symbol = symbol.strip().upper()
        if not symbol:
            raise MarketDataError("Ticker cannot be empty")
        try:
            raw = self.downloader(tickers=symbol, period=period, interval=interval, progress=False, auto_adjust=False)
        except Exception as exc:
            raise MarketDataError(f"Unable to download {symbol} data: {exc}") from exc
        if raw is None or raw.empty:
            limit = INTRADAY_PERIOD_LIMITS.get(interval)
            hint = ""
            if limit:
                hint = f" For {interval} data, Yahoo typically limits lookback to about {limit}."
            raise MarketDataError(
                f"No data returned for {symbol}. Check symbol spelling and period/interval combination.{hint}"
            )
        frame = normalize_ohlcv(raw)
        if len(frame) < minimum_rows:
            raise MarketDataError(f"Only {len(frame)} valid rows returned; at least {minimum_rows} are required")
        return frame
