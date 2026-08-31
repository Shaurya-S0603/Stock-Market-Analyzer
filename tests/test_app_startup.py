from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def test_fresh_app_renders_portfolio_onboarding_without_exception(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PAPER_DB_PATH", str(tmp_path / "fresh-paper.db"))
    app = AppTest.from_file(APP_PATH, default_timeout=20).run()
    assert not app.exception
