"""QuantEdge v3 FastAPI foundation: isolated, read-only synthetic market demo.

The API exposes no accounts, arbitrary user code, shared portfolio writes,
brokerage actions, or provider secrets. Production accounts come only after
authentication, per-user storage and database isolation have been tested.
"""
from __future__ import annotations

from functools import lru_cache
import os
import math
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from stockmarket.workspace.demo_data import synthetic_demo_bars
from stockmarket.workspace.indicators import ema, rsi, sma
from stockmarket.workspace.strategy_backtest import run_backtest
from stockmarket.workspace.strategy_schema import example_strategy
from apps.api.historical import historical_ohlcv

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


def _demo_strategy():
    # Keep the strategy symbol consistent with its entirely fictional price series.
    return example_strategy().model_copy(update={"symbol": DEMO_SYMBOL})


class DemoRequest(BaseModel):
    """Bound inputs so demo endpoints cannot trigger expensive arbitrary work."""
    model_config = ConfigDict(extra="forbid")
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


@app.get("/api/v1/health/dependencies")
def dependency_health() -> dict:
    """Actually probe configured PostgreSQL and Redis, without leaking credentials.

    The foundation does NOT write user data to these services yet.
    """
    from sqlalchemy import create_engine, text
    import redis

    states: dict[str, str] = {"postgres": "not configured", "redis": "not configured"}
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        engine = None
        try:
            engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
            with engine.connect() as connection:
                if connection.execute(text("SELECT 1")).scalar() != 1:
                    raise ValueError("Unexpected database response")
            states["postgres"] = "connected"
        except Exception:
            states["postgres"] = "unavailable"
        finally:
            if engine is not None:
                engine.dispose()

    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        client = None
        try:
            client = redis.Redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3)
            states["redis"] = "connected" if client.ping() else "unavailable"
        except Exception:
            states["redis"] = "unavailable"
        finally:
            if client is not None:
                client.close()

    ready = all(value != "unavailable" for value in states.values())
    return JSONResponse(
        {"status": "ok" if ready else "degraded",
         "dependencies": states,
         "note": "Connectivity probe only. Database-backed user persistence is a later phase."},
        status_code=200 if ready else 503,
    )


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
def history(symbol: str, interval: Literal["1d"] = "1d",
            period: Literal["3mo", "6mo", "1y"] = "6mo") -> dict:
    if symbol.upper() != DEMO_SYMBOL:
        return historical_ohlcv(symbol, period)
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
    data = _demo_strategy().model_dump(mode="json")
    return {"strategy": data, "label": "Illustrative rule set only; no trades are submitted."}


@app.post("/api/v1/backtests/demo")
def backtest_demo(payload: DemoRequest) -> dict:
    result = run_backtest(_demo(), _demo_strategy(), starting_cash=payload.starting_cash)
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
