"""Cross-service smoke checks through Next.js to FastAPI (no provider API calls).

This script probes an ACTUAL running HTTP Next.js server which must connect
to the separate FastAPI server. It never sends orders or financial credentials.
"""
from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(base: str, path: str, *, body: dict | None = None,
            expected: int = 200) -> dict:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"content-type": "application/json"} if payload is not None else {}
    req = Request(base + path, data=payload, headers=headers,
                  method="POST" if payload is not None else "GET")
    try:
        with urlopen(req, timeout=8) as response:
            status = response.status
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        status = exc.code
        result = json.loads(exc.read().decode("utf-8"))
    if status != expected:
        raise AssertionError(f"{path}: expected HTTP {expected}, got {status}: {result}")
    return result


def verify(base: str, *, with_services: bool = False) -> None:
    deadline = time.monotonic() + 45
    while True:
        try:
            health = request(base, "/api/v1/health")
            if health["service"] == "quantedge-api":
                break
        except (URLError, AssertionError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    assert health["brokerage"] == "disabled"
    assert health["database"] == "not-connected-in-foundation"

    history = request(base, "/api/v1/market/QEDMO/ohlcv")
    assert history["provenance"]["fictional"] is True
    assert history["provenance"]["provider"] == "synthetic-tutorial"
    assert len(history["bars"]) == 320
    assert all(bar["high"] >= max(bar["open"], bar["close"]) and
               bar["low"] <= min(bar["open"], bar["close"]) for bar in history["bars"])

    values = request(base, "/api/v1/market/QEDMO/indicators?period=20")
    assert len(values["indicators"]["sma"]) == 301
    assert values["fictional"]
    assert "error" in request(base, "/api/v1/market/!oops/ohlcv", expected=400)
    assert "detail" in request(base, "/api/v1/market/AAPL/ohlcv", expected=404)

    backtest = request(base, "/api/v1/backtests/demo", body={"starting_cash": 10000})
    assert backtest["fictional"] and backtest["symbol"] == "QEDMO"
    assert len(backtest["equity"]) == 320
    assert backtest["metrics"]["final_equity"] > 0
    assert all(trade["symbol"] == "QEDMO" for trade in backtest["trades"])
    assert request(base, "/api/v1/backtests/demo", body={"starting_cash": -1},
                   expected=400)["error"]
    print("PASS: Next.js -> FastAPI health, OHLCV, indicators, bounded backtest and no real symbols")

    if with_services:
        dependency = request(base, "/api/v1/health/dependencies")
        # URL path for dependency probe is not in public BFF yet. Test directly in
        # a separate backend check instead of weakening the BFF allowlist.
        assert dependency["status"] == "ok"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3000")
    args = parser.parse_args()
    verify(args.base.rstrip("/"))
