"""Contract, numerical consistency, validation and paper-only security tests."""
from fastapi.testclient import TestClient

from apps.api.main import app
from stockmarket.workspace.demo_data import synthetic_demo_bars

client = TestClient(app)


def test_health_does_not_claim_database_or_broker_connectivity():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "not-connected-in-foundation"
    assert data["brokerage"] == "disabled"


def test_demo_candles_are_constrained_and_labelled_fictional():
    response = client.get("/api/v1/market/QEDMO/ohlcv")
    assert response.status_code == 200
    data = response.json()
    assert data["provenance"]["fictional"] is True
    assert data["provenance"]["provider"] == "synthetic-tutorial"
    assert len(data["bars"]) == 320
    assert all(bar["high"] >= max(bar["open"], bar["close"]) for bar in data["bars"])
    assert all(bar["low"] <= min(bar["open"], bar["close"]) for bar in data["bars"])


def test_missing_symbols_dont_get_fake_quotes():
    assert client.get("/api/v1/market/MSFT/ohlcv").status_code == 404
    assert client.get("/api/v1/market/MSFT/indicators").status_code == 404
    assert client.get("/api/v1/market/QEDMO/ohlcv?interval=1m").status_code == 422


def test_causal_indicator_warmup_and_api_envelope():
    result = client.get("/api/v1/market/QEDMO/indicators?period=30")
    assert result.status_code == 200
    data = result.json()
    assert len(data["indicators"]["sma"]) == 320 - 30 + 1
    assert data["fictional"] is True
    assert client.get("/api/v1/market/QEDMO/indicators?period=0").status_code == 422


def test_demo_backtest_is_repeatable_and_bounded():
    a = client.post("/api/v1/backtests/demo", json={"starting_cash": 10000})
    b = client.post("/api/v1/backtests/demo", json={"starting_cash": 10000})
    assert a.status_code == b.status_code == 200
    first, second = a.json(), b.json()
    assert first == second
    assert first["fictional"] is True
    assert len(first["equity"]) == 320
    assert first["metrics"]["final_equity"] > 0
    assert "next bar open" in first["execution"]
    assert client.post("/api/v1/backtests/demo", json={"starting_cash": -1}).status_code == 422
    assert client.post("/api/v1/backtests/demo", json={"starting_cash": 1e20}).status_code == 422
    assert client.post("/api/v1/backtests/demo", json={"starting_cash": "NaN"}).status_code == 422
