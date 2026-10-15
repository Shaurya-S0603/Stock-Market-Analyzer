"""End-to-end live HTTP acceptance probe for the Next.js BFF → FastAPI chain."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

BACKEND = "http://127.0.0.1:8000"
FRONTEND = "http://127.0.0.1:3000"


def get_json(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=8) as result:
        assert result.status == 200
        return json.load(result)


def check() -> None:
    backend = get_json(BACKEND, "/api/v1/health")
    frontend = get_json(FRONTEND, "/api/v1/health")
    assert backend == frontend
    assert backend["status"] == "ok" and backend["brokerage"] == "disabled"

    storage = get_json(BACKEND, "/api/v1/health/dependencies")
    assert storage["dependencies"] == {"postgres": "connected", "redis": "connected"}

    for base in [BACKEND, FRONTEND]:
        candles = get_json(base, "/api/v1/market/QEDMO/ohlcv")
        assert candles["provenance"]["fictional"] is True
        assert len(candles["bars"]) == 320
        indicator = get_json(base, "/api/v1/market/QEDMO/indicators?period=20")
        assert len(indicator["indicators"]["sma"]) == 301
        payload = json.dumps({"starting_cash": 10000}).encode("utf-8")
        request = urllib.request.Request(
            base + "/api/v1/backtests/demo", data=payload,
            headers={"content-type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=12) as reply:
            backtest = json.load(reply)
            assert reply.status == 200
        assert backtest["fictional"] is True
        assert len(backtest["equity"]) == 320

    try:
        get_json(FRONTEND, "/api/v1/market/MSFT/ohlcv")
    except urllib.error.HTTPError as error:
        assert error.code == 404
    else:
        raise AssertionError("An unsupported real symbol returned invented data")

    with urllib.request.urlopen(FRONTEND + "/", timeout=8) as response:
        html = response.read().decode("utf-8")
        assert response.status == 200
        assert "Personal market terminal" in html
        assert "QuantEdge" in html

    print("PASS: Python API, PostgreSQL, Redis, Next BFF, indicators, backtest and web document")


if __name__ == "__main__":
    check()
