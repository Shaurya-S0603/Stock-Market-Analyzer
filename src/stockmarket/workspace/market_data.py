"""Yahoo adapter, strict OHLCV normalization, and explicit cache provenance."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .database import WorkspaceDB, clean_symbol

OHLCV = ("open", "high", "low", "close", "volume")
VALID_INTERVALS = {"1m", "5m", "15m", "1h", "1d", "1wk", "1mo"}
# Provider retention is subject to change; fail closed on unsupported extended intraday lookbacks.
INTRADAY_MAX_DAYS = {"1m": 7, "5m": 60, "15m": 60, "1h": 60}
PERIOD_DAYS = {"1d": 1, "5d": 5, "7d": 7, "1mo": 31, "3mo": 93,
               "6mo": 186, "1y": 366, "2y": 732, "5y": 1830, "max": 999999,
               "30d": 30, "60d": 60}


class MarketDataError(RuntimeError):
    pass


def validate_history(raw: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Reject inconsistent bars rather than inventing or silently fixing prices."""
    if interval not in VALID_INTERVALS:
        raise MarketDataError("Unsupported timeframe: " + interval)
    if raw is None or raw.empty:
        raise MarketDataError("No historical bars were returned")
    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame.columns = [str(c).lower() for c in frame.columns]
    if frame.columns.duplicated().any():
        raise MarketDataError("Duplicate OHLCV columns")
    if any(column not in frame for column in OHLCV):
        raise MarketDataError("OHLCV data is missing required columns")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise MarketDataError("Historical prices must have datetime timestamps")
    if frame.index.has_duplicates:
        raise MarketDataError("Duplicate market timestamps")
    if frame.index.tz is None:
        if interval in INTRADAY_MAX_DAYS:
            raise MarketDataError("Intraday timestamps must include the exchange timezone")
        # Daily/weekly/monthly date labels are sessions, not claimed intraday quote times.
        frame.index = frame.index.tz_localize("UTC")
    else:
        frame.index = frame.index.tz_convert("UTC")
    frame = frame.loc[:, list(OHLCV)].sort_index()
    for col in OHLCV:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise MarketDataError("Prices contain missing or non-finite numbers")
    if (frame["open"] <= 0).any() or (frame["close"] <= 0).any() or (frame["low"] <= 0).any():
        raise MarketDataError("Nonpositive OHLC prices")
    if (frame["volume"] < 0).any():
        raise MarketDataError("Negative volume")
    if ((frame["high"] < frame[["open", "close", "low"]].max(axis=1)) |
        (frame["low"] > frame[["open", "close", "high"]].min(axis=1))).any():
        raise MarketDataError("Inconsistent OHLC values")
    frame.index.name = "timestamp"
    return frame


def validate_request(period: str, interval: str) -> None:
    if interval not in VALID_INTERVALS:
        raise MarketDataError("Unsupported interval: " + interval)
    if period not in PERIOD_DAYS:
        raise MarketDataError("Unsupported period: " + period)
    maximum = INTRADAY_MAX_DAYS.get(interval)
    if maximum and PERIOD_DAYS[period] > maximum:
        raise MarketDataError(
            f"{interval} data is restricted to at most {maximum} days by this free adapter; choose a shorter period."
        )


class YahooMarketAdapter:
    name = "yfinance"

    def __init__(self, downloader: Callable | None = None):
        self.downloader = downloader

    def get_history(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        validate_request(period, interval)
        symbol = clean_symbol(symbol)
        downloader = self.downloader
        if downloader is None:
            import yfinance as yf
            downloader = yf.download
        try:
            bars = downloader(
                tickers=symbol, period=period, interval=interval,
                progress=False, auto_adjust=False, threads=False,
            )
        except Exception as exc:
            raise MarketDataError(f"Market provider error for {symbol}: {exc}") from exc
        return validate_history(bars, interval)

    def search(self, query: str) -> list[dict]:
        query = str(query).strip()
        if not query:
            return []
        try:
            import yfinance as yf
            result = yf.Search(query, max_results=10, news_count=0)
            return [
                {"symbol": item.get("symbol", ""), "name": item.get("shortname") or item.get("longname") or "",
                 "exchange": item.get("exchange", "")}
                for item in result.quotes if item.get("symbol")
            ]
        except Exception as exc:
            raise MarketDataError("Symbol search is temporarily unavailable: " + str(exc)) from exc


@dataclass(frozen=True)
class HistoryResult:
    frame: pd.DataFrame
    provider: str
    origin: str
    warning: str = ""




@dataclass(frozen=True)
class HistoricalQuote:
    """A cached historical close, explicitly NOT a live market quotation."""
    symbol: str
    price: float
    change: float | None
    change_pct: float | None
    observed_at: str
    provider: str
    origin: str = "saved historical close"


class MarketDataService:
    def __init__(self, storage: WorkspaceDB, provider: YahooMarketAdapter | None = None):
        self.storage = storage
        self.provider = provider or YahooMarketAdapter()


    def saved_quote(self, symbol: str) -> HistoricalQuote:
        clean = clean_symbol(symbol)
        candles = self.storage.load_candles(clean, "1d")
        if candles.empty:
            raise MarketDataError("No saved historical daily quote for " + clean)
        last = float(candles["close"].iloc[-1])
        previous = float(candles["close"].iloc[-2]) if len(candles) > 1 else None
        change = last - previous if previous is not None else None
        change_pct = change / previous * 100 if previous else None
        return HistoricalQuote(
            symbol=clean, price=last, change=change, change_pct=change_pct,
            observed_at=candles.index[-1].isoformat(),
            provider=str(candles["provider"].iloc[-1]),
        )

    def history(self, symbol: str, *, period: str = "6mo", interval: str = "1d",
                refresh: bool = False, offline: bool = False) -> HistoryResult:
        validate_request(period, interval)
        clean = clean_symbol(symbol)
        cached = self.storage.load_candles(clean, interval)
        if not refresh and not cached.empty:
            return HistoryResult(cached, str(cached["provider"].iloc[-1]), "cached",
                                 "Historical cache. Press Refresh data for new provider observations.")
        if offline:
            if cached.empty:
                raise MarketDataError("No locally cached candles for this symbol and interval")
            return HistoryResult(cached, str(cached["provider"].iloc[-1]), "cached",
                                 "Offline: showing previously saved historical prices.")
        try:
            frame = self.provider.get_history(clean, period, interval)
        except (MarketDataError, ValueError) as exc:
            if cached.empty:
                raise MarketDataError(str(exc)) from exc
            return HistoryResult(cached, str(cached["provider"].iloc[-1]), "cached-fallback",
                                 "Provider unavailable; displaying saved candles only. " + str(exc))
        self.storage.save_candles(clean, interval, frame, provider=self.provider.name)
        return HistoryResult(self.storage.load_candles(clean, interval), self.provider.name, "provider",
                             "Provider bars are historical; the final bar may still be forming.")
