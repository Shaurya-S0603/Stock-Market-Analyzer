"""Offline Streamlit smoke tests for all new Phase 3 pages."""
import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("func", [
    "strategy_builder_page", "strategy_backtesting_page", "backtest_comparison_page",
])
def test_strategy_pages_render_without_paper_account(func, tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTEDGE_WORKSPACE_DB", str(tmp_path/"testing.db"))
    monkeypatch.setenv("PAPER_DB_PATH", str(tmp_path/"unused-paper.db"))
    script = f"from stockmarket.workspace.strategy_pages import {func}\n{func}()\n"
    app = AppTest.from_string(script, default_timeout=25).run()
    assert not app.exception
