"""Full app starts directly with research, no legacy onboarding or broker."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP_PATH=Path(__file__).resolve().parents[1]/"app.py"

def test_fresh_app_starts_on_overview_without_exception(tmp_path,monkeypatch):
    monkeypatch.setenv("QUANTEDGE_WORKSPACE_DB",str(tmp_path/"workspace.db"))
    monkeypatch.setenv("PAPER_DB_PATH",str(tmp_path/"unused-legacy.db"))
    app=AppTest.from_file(APP_PATH,default_timeout=30).run()
    assert not app.exception
    assert any("Personal Market Workspace" in title.value for title in app.title)
