"""Offline Phase 0/1 tests: persistence, data integrity, and provider fallback."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from stockmarket.workspace import (
    WorkspaceDB, MarketDataError, MarketDataService, YahooMarketAdapter, validate_history,
)


def sample_bars(periods: int = 70, interval: str = "1d"):
    freq = "D" if interval == "1d" else "h"
    index = pd.date_range("2026-01-01", periods=periods, freq=freq, tz="America/New_York")
    close = pd.Series([100 + index * 0.2 for index in range(periods)], index=index)
    return pd.DataFrame({
        "Open": close - 0.1, "High": close + 1, "Low": close - 1,
        "Close": close, "Volume": 100_000,
    }, index=index)


def test_watchlists_survive_restart_without_affecting_paper_database(tmp_path):
    path = tmp_path / "research.db"
    db = WorkspaceDB(str(path))
    first = db.default_watchlist()
    db.add_to_watchlist(first, "msft")
    db.add_to_watchlist(first, "MSFT")
    second = db.create_watchlist("Long-term")
    db.add_to_watchlist(second, "aapl")
    db.rename_watchlist(second, "Investing")
    recovered = WorkspaceDB(str(path))
    assert recovered.symbols_in_watchlist(first) == ["MSFT"]
    assert recovered.symbols_in_watchlist(second) == ["AAPL"]
    assert {v["name"] for v in recovered.list_watchlists()} == {"My Watchlist", "Investing"}
    recovered.delete_watchlist(second)
    assert recovered.symbols_in_watchlist(first) == ["MSFT"]
    assert not (tmp_path / "paper_trading.db").exists()


def test_market_history_is_normalized_and_cached_without_network(tmp_path):
    calls = []
    def downloader(**kwargs):
        calls.append(kwargs)
        return sample_bars()
    adapter = YahooMarketAdapter(downloader)
    store = WorkspaceDB(str(tmp_path / "market.db"))
    service = MarketDataService(store, adapter)
    original = service.history("MSFT", interval="1d", period="6mo", refresh=True)
    assert original.origin == "provider"
    assert original.frame.index.tz is not None
    assert len(calls) == 1
    cached = service.history("msft", interval="1d", period="6mo", offline=True)
    assert len(calls) == 1
    assert cached.origin == "cached"
    assert cached.frame.index.equals(original.frame.index)
    service.history("MSFT", interval="1d", period="6mo", refresh=True)
    assert len(store.load_candles("MSFT", "1d")) == len(original.frame)  # idempotent upsert


def test_provider_failure_uses_explicit_cached_fallback(tmp_path):
    db = WorkspaceDB(str(tmp_path / "market.db"))
    MarketDataService(db, YahooMarketAdapter(lambda **kw: sample_bars())).history(
        "AAPL", interval="1d", period="6mo", refresh=True
    )
    def broken(**kwargs):
        raise OSError("offline")
    result = MarketDataService(db, YahooMarketAdapter(broken)).history(
        "AAPL", interval="1d", period="6mo", refresh=True
    )
    assert result.origin == "cached-fallback"
    assert "Provider unavailable" in result.warning


def test_invalid_history_and_unsupported_provider_windows_are_rejected(tmp_path):
    bad = sample_bars()
    bad.iloc[0, bad.columns.get_loc("High")] = 1
    with pytest.raises(MarketDataError, match="Inconsistent"):
        validate_history(bad, "1d")
    repeated = pd.concat([sample_bars(), sample_bars().iloc[-1:]])
    with pytest.raises(MarketDataError, match="Duplicate"):
        validate_history(repeated, "1d")
    naive = sample_bars(interval="1h").tz_localize(None)
    with pytest.raises(MarketDataError, match="timezone"):
        validate_history(naive, "1h")
    store = WorkspaceDB(str(tmp_path / "market.db"))
    with pytest.raises(MarketDataError, match="restricted"):
        MarketDataService(store).history("MSFT", period="6mo", interval="1h", refresh=True)
    assert store.cached_symbols() == []


def test_workspace_database_does_not_reset_existing_candles(tmp_path):
    db = WorkspaceDB(str(tmp_path / "market.db"))
    validated = validate_history(sample_bars(), "1d")
    db.save_candles("MSFT", "1d", validated, provider="test")
    second_session = WorkspaceDB(str(tmp_path / "market.db"))
    assert len(second_session.load_candles("MSFT", "1d")) == 70


def test_primary_app_entrypoint_exists():
    assert Path("app.py").is_file()


def test_fresh_streamlit_app_opens_market_explorer_without_paper_account(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("QUANTEDGE_WORKSPACE_DB", str(tmp_path / "new-workspace.db"))
    monkeypatch.setenv("PAPER_DB_PATH", str(tmp_path / "unused-paper.db"))
    app = AppTest.from_file(Path("app.py").resolve(), default_timeout=20).run()
    assert not app.exception
    assert any("Personal Market Workspace" in item.value for item in app.title)
    assert (tmp_path / "new-workspace.db").exists()


def test_saved_quote_never_claims_to_be_realtime(tmp_path):
    db = WorkspaceDB(str(tmp_path / "market.db"))
    service = MarketDataService(db, YahooMarketAdapter(lambda **kw: sample_bars()))
    with pytest.raises(MarketDataError, match="No saved"):
        service.saved_quote("MSFT")
    service.history("MSFT", period="6mo", interval="1d", refresh=True)
    quote = service.saved_quote("MSFT")
    assert quote.origin == "saved historical close"
    assert quote.change is not None and quote.change > 0
    assert quote.change_pct is not None and quote.change_pct > 0
    assert quote.observed_at.endswith("+00:00")
