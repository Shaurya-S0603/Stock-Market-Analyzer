"""Streamlit Phase 2 page smoke tests without market-network dependencies."""
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from stockmarket.workspace import WorkspaceDB


@pytest.mark.parametrize("page", [
    "chart_terminal_page", "stock_research_page", "screener_page",
])
def test_phase2_pages_render_offline(page, tmp_path, monkeypatch):
    db_path = tmp_path / "phase2.db"
    db = WorkspaceDB(str(db_path))
    if page == "chart_terminal_page":
        prices = 100 + np.arange(80) * 0.3
        frame = pd.DataFrame({
            "open": prices, "high": prices + 1, "low": prices - 1,
            "close": prices, "volume": np.full(80, 1500)
        }, index=pd.date_range("2026-01-01", periods=80, freq="d", tz="UTC"))
        db.save_candles("MSFT", "1d", frame, provider="offline-test")
    monkeypatch.setenv("QUANTEDGE_WORKSPACE_DB", str(db_path))
    script = f"from stockmarket.workspace.pages import {page}\n{page}()\n"
    app = AppTest.from_string(script, default_timeout=25).run()
    assert not app.exception
