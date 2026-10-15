"""QuantEdge v3 FastAPI foundation: isolated, read-only synthetic market demo.

The API exposes no accounts, arbitrary user code, shared portfolio writes,
brokerage actions, or provider secrets. Production accounts come only after
authentication, per-user storage and database isolation have been tested.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import math
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from stockmarket.workspace.demo_data import synthetic_demo_bars
from stockmarket.workspace.indicators import ema, rsi, sma
from stockmarket.workspace.strategy_backtest import run_backtest
from stockmarket.workspace.strategy_schema import example_strategy

app = FastAPI(
    title="QuantEdge Research API",
    version="3.0.0-alpha.0",
    description="Personal education, historical research and fictional paper simulations only.",
    docs_url="/docs",
    redoc_url=None,
)

DEMO_SYMBOL = "QEDMO"
SOURCE = "synthetic-tutorial"


@lru_cache(maxsize=1)
def _demo():
    return synthetic_demo_bars()


class DemoRequest(BaseModel):
    """Bound inputs so demo endpoints cannot trigger expensive arbitrary work."""
    starting_cash: float = Field(default=10000, ge=100, le=1_000_000, allow_inf_nan=False)


@app.get("/api/v1/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "quantedge-api",
        "api_version": "v1",
        "market_mode": "fictional-demo-only",
        "database": "not-connected-in-foundation",
        "brokerage": "disabled",
    }


@app.get("/api/v1/symbols")
def symbols() -> dict:
    return {
        "symbols": [
            {"ticker": DEMO_SYMBOL, "name": "Synthetic Tutorial Example",
             "asset_class": "fictional", "provider": SOURCE}
        ],
        "warning": "Only a fictional symbol is exposed in the foundation stage.",
    }


@app.get("/api/v1/market/{symbol}/ohlcv")
def history(symbol: str, interval: Literal["1d"] = "1d") -> dict:
    if symbol.upper() != DEMO_SYMBOL:
        raise HTTPException(
            status_code=404,
            detail="Historical provider ingestion is not yet connected. Only fictional QEDMO is supported.",
        )
    frame = _demo()
    bars = [
        {
            "time": stamp.strftime("%Y-%m-%d"),
            "timestamp": stamp.isoformat(),
            "open": round(float(row["open"]), 6),
            "high": round(float(row["high"]), 6),
            "low": round(float(row["low"]), 6),
            "close": round(float(row["close"]), 6),
            "volume": int(row["volume"]),
        }
        for stamp, row in frame.iterrows()
    ]
    return {
        "symbol": DEMO_SYMBOL, "interval": interval, "bars": bars,
        "provenance": {"provider": SOURCE, "fictional": True, "adjustment": "not-applicable",
                       "as_of": bars[-1]["timestamp"], "latest_bar_complete": True},
        "warning": "This is fictional, non-tradable OHLCV. It is not an exchange quote.",
    }


@app.get("/api/v1/market/{symbol}/indicators")
def indicators(symbol: str, period: int = Query(default=20, ge=2, le=250)) -> dict:
    if symbol.upper() != DEMO_SYMBOL:
        raise HTTPException(status_code=404, detail="Only fictional QEDMO is supported in this stage")
    frame = _demo()
    result = {}
    for key, indicator in [
        ("sma", sma(frame, period)), ("ema", ema(frame, period)), ("rsi", rsi(frame, 14)),
    ]:
        result[key] = [
            {"time": ts.strftime("%Y-%m-%d"), "value": round(float(value), 5)}
            for ts, value in indicator.items()
            if math.isfinite(float(value))
        ]
    return {"symbol": DEMO_SYMBOL, "period": period, "indicators": result,
            "provenance": "synthetic-tutorial", "fictional": True}


@app.get("/api/v1/strategies/example")
def strategy_example() -> dict:
    data = example_strategy().model_dump(mode="json")
    return {"strategy": data, "label": "Illustrative rule set only; no trades are submitted."}


@app.post("/api/v1/backtests/demo")
def backtest_demo(payload: DemoRequest) -> dict:
    result = run_backtest(_demo(), example_strategy(), starting_cash=payload.starting_cash)
    return {
        "symbol": DEMO_SYMBOL,
        "fictional": True, "provider": SOURCE,
        "strategy": result["strategy_snapshot"]["name"],
        "metrics": result["metrics"],
        "trades": result["trades"],
        "equity": [{"time": row["timestamp"][:10], "equity": row["equity"],
                    "drawdown_pct": row["drawdown_pct"]} for row in result["equity"]],
        "execution": result["metadata"]["execution"],
        "warning": "Fictional historical simulation only. No real orders or profit forecast.",
    }
