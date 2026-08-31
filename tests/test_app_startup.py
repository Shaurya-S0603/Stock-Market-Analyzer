from __future__ import annotations

from streamlit.testing.v1 import AppTest


def test_fresh_app_renders_portfolio_onboarding_without_exception(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PAPER_DB_PATH", str(tmp_path / "fresh-paper.db"))
    app = AppTest.from_file("streamlit_app.py", default_timeout=20).run()
    assert not app.exception
