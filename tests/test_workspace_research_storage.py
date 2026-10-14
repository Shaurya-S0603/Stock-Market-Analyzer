"""Research configuration and screener regression tests. No external HTTP calls."""
import numpy as np
import pandas as pd
import pytest

from stockmarket.workspace import WorkspaceDB
from stockmarket.workspace.indicators import sma
from stockmarket.workspace.research_storage import ResearchRepository, validate_chart, validate_screener
from stockmarket.workspace.screener import screen_cached


def test_chart_layout_and_screener_survive_restart(tmp_path):
    path = tmp_path / "workspace.db"
    repo = ResearchRepository(WorkspaceDB(str(path)))
    layout = {"symbol": "msft", "interval": "1d", "indicators": ["SMA", "RSI"], "chart_type": "Candles"}
    first = repo.save("chart", "Momentum", layout)
    assert repo.list("chart")[0]["configuration"]["symbol"] == "MSFT"
    repo.save("chart", "Updated", {**layout, "indicators": ["EMA", "MACD"]}, first)
    other = repo.save("screener", "My scan", {"filters": {"min_price": 50, "rsi_max": 75}})
    restarted = ResearchRepository(WorkspaceDB(str(path)))
    assert restarted.list("chart")[0]["name"] == "Updated"
    assert restarted.list("screener")[0]["id"] == other
    with pytest.raises(ValueError, match="already"):
        restarted.save("chart", "Updated", layout)
    restarted.delete("chart", first)
    assert restarted.list("chart") == []
    assert restarted.list("screener")


def test_chart_and_screener_json_reject_unsupported_rules():
    with pytest.raises(ValueError, match="Unknown"):
        validate_chart({"symbol": "AAPL", "arbitrary_code": "exec"})
    with pytest.raises(ValueError, match="indicator"):
        validate_chart({"indicators": ["UNSUPPORTED"]})
    with pytest.raises(ValueError, match="Unsupported screener"):
        validate_screener({"filters": {"python": 1}})
    with pytest.raises(ValueError, match="exceed"):
        validate_screener({"filters": {"min_price": 100, "max_price": 50}})


def test_cached_screener_enforces_missing_history_and_thresholds(tmp_path):
    db = WorkspaceDB(str(tmp_path / "workspace.db"))
    ix = pd.date_range("2026-01-01", periods=60, freq="D", tz="UTC")
    for symbol, base in [("AAPL", 100.0), ("MSFT", 20.0)]:
        prices = base + np.arange(60, dtype=float) * (1 if symbol == "AAPL" else -0.1)
        frame = pd.DataFrame({"open":prices, "high":prices+2, "low":prices-2,
                              "close":prices, "volume":10000}, index=ix)
        db.save_candles(symbol, "1d", frame, provider="offline")
    results = screen_cached(db, ["AAPL", "MSFT", "UNAVAILABLE"], {
        "filters": {"min_price": 50, "above_sma": 20, "rsi_min": 50},
    })
    assert results["Symbol"].tolist() == ["AAPL"]
    assert screen_cached(db, ["UNAVAILABLE"], {"filters": {}}).empty
    assert sma(db.load_candles("AAPL", "1d"), 20).iloc[-1] < 159
