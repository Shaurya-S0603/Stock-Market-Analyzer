"""Opt-in read-only historical bars. No brokerage quotes or account state."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
import os
import re
import threading
import time

from fastapi import HTTPException
from stockmarket.workspace.market_data import (
    MarketDataError, YahooMarketAdapter, validate_history,
)

# This public-facing demonstration adapter is DISABLED by default.
# Enable only for controlled local development until auth/rate limits are durable.
_ALLOWED_PERIODS = frozenset({"3mo", "6mo", "1y"})
_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9.\^=-]{0,14}$")
_TTL_SECONDS = 300
_MAX_CACHE_ENTRIES = 64
_cache: OrderedDict[tuple[str, str], tuple[float, dict]] = OrderedDict()
_cache_lock = threading.Lock()
_provider_slots = threading.BoundedSemaphore(2)


def clear_cache() -> None:
    """Used in offline contract tests; never affects the older Streamlit cache."""
    with _cache_lock:
        _cache.clear()


def historical_ohlcv(symbol: str, period: str) -> dict:
    if os.getenv("QUANTEDGE_ENABLE_HISTORICAL_RESEARCH", "0") != "1":
        raise HTTPException(status_code=404, detail="Historical adapter is disabled")
    ticker = symbol.strip().upper()
    if not _SYMBOL.fullmatch(ticker) or period not in _ALLOWED_PERIODS:
        raise HTTPException(status_code=422, detail="Unsupported symbol or historical period")

    key = (ticker, period)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached is not None and cached[0] > now:
            _cache.move_to_end(key)
            return cached[1]
        if cached is not None:
            del _cache[key]

    if not _provider_slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Historical provider is busy; retry later")
    try:
        # The existing Streamlit adapter already validates the response, but
        # explicitly revalidate its bars so provider mocks obey the same contract.
        try:
            raw = YahooMarketAdapter().get_history(ticker, period=period, interval="1d")
            frame = validate_history(raw, "1d")
        except (MarketDataError, ValueError, KeyError, TypeError, ImportError) as exc:
            raise HTTPException(
                status_code=503, detail="Historical data is unavailable from the free provider"
            ) from exc
        if len(frame) > 400:
            frame = frame.tail(400)
        rows = [
            {
                "time": ts.strftime("%Y-%m-%d"),
                "timestamp": ts.isoformat(),
                "open": round(float(row["open"]), 6),
                "high": round(float(row["high"]), 6),
                "low": round(float(row["low"]), 6),
                "close": round(float(row["close"]), 6),
                "volume": int(row["volume"]),
            }
            for ts, row in frame.iterrows()
        ]
        if not rows:
            raise HTTPException(status_code=503, detail="No historical bars were returned")
        response = {
            "symbol": ticker, "interval": "1d", "period": period, "bars": rows,
            "provenance": {
                "provider": "yfinance / Yahoo Finance (unofficial free historical adapter)",
                "fictional": False,
                "adjustment": "auto_adjust=False; provider corporate-action adjustments may still apply",
                "as_of": rows[-1]["timestamp"],
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "latest_bar_complete": None,
                "timestamp_semantics": "UTC date labels represent market sessions, not live quote times",
                "delay": "Provider/exchange delay unknown; not guaranteed current or executable",
            },
            "warning": (
                "Historical research only; availability and accuracy are not guaranteed. "
                "The latest daily candle can be incomplete. No live or brokerage quote."
            ),
        }
        with _cache_lock:
            _cache[key] = (time.monotonic() + _TTL_SECONDS, response)
            _cache.move_to_end(key)
            while len(_cache) > _MAX_CACHE_ENTRIES:
                _cache.popitem(last=False)
        return response
    finally:
        _provider_slots.release()
