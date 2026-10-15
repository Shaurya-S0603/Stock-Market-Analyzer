"""Phase 1A: offline historical-provider contract and feature-flag tests."""
import pandas as pd
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api import historical

client = TestClient(app)


def fake_frame():
    return pd.DataFrame(
        {
            "open": [100.0, 102.0, 103.0, 104.0],
            "high": [104.0, 105.0, 106.0, 107.0],
            "low": [99.0, 101.0, 102.0, 103.0],
            "close": [102.0, 103.0, 104.0, 106.0],
            "volume": [100, 200, 300, 400],
        },
        index=pd.date_range("2026-09-01", periods=4, tz="UTC"),
    )


def test_provider_is_opt_in(monkeypatch):
    monkeypatch.delenv("QUANTEDGE_ENABLE_HISTORICAL_RESEARCH", raising=False)
    historical.clear_cache()
    assert client.get("/api/v1/market/MSFT/ohlcv").status_code == 404


def test_mocked_read_only_data_with_provenance_and_cache(monkeypatch):
    monkeypatch.setenv("QUANTEDGE_ENABLE_HISTORICAL_RESEARCH", "1")
    historical.clear_cache()
    calls = []

    def mock_history(self, symbol, period, interval):
        calls.append((symbol, period, interval))
        return fake_frame()

    monkeypatch.setattr(historical.YahooMarketAdapter, "get_history", mock_history)
    a = client.get("/api/v1/market/MSFT/ohlcv?period=3mo")
    b = client.get("/api/v1/market/MSFT/ohlcv?period=3mo")
    assert a.status_code == b.status_code == 200
    result = a.json()
    assert calls == [("MSFT", "3mo", "1d")]
    assert result == b.json()
    assert result["provenance"]["fictional"] is False
    assert result["provenance"]["latest_bar_complete"] is None
    assert len(result["bars"]) == 4
    assert "Historical research only" in result["warning"]
    assert result["bars"][0]["time"] == "2026-09-01"


def test_bad_queries_rejected_before_provider(monkeypatch):
    monkeypatch.setenv("QUANTEDGE_ENABLE_HISTORICAL_RESEARCH", "1")
    historical.clear_cache()
    assert client.get("/api/v1/market/MSFT/ohlcv?period=max").status_code == 422
    assert client.get("/api/v1/market/MSFT/ohlcv?interval=1m").status_code == 422
    assert client.get("/api/v1/market/thissymboliswaytoolong/ohlcv").status_code == 422
    assert client.get("/api/v1/market/QEDMO/ohlcv").json()["provenance"]["fictional"] is True


def test_provider_failure_is_sanitized(monkeypatch):
    monkeypatch.setenv("QUANTEDGE_ENABLE_HISTORICAL_RESEARCH", "1")
    historical.clear_cache()

    def broken_provider(self, symbol, period, interval):
        raise historical.MarketDataError("secret upstream exception")

    monkeypatch.setattr(historical.YahooMarketAdapter, "get_history", broken_provider)
    result = client.get("/api/v1/market/TSLA/ohlcv")
    assert result.status_code == 503
    assert "secret" not in result.text
