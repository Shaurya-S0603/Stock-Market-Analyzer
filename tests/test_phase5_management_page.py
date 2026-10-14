"""Offline startup smoke and navigation for Data Management."""
from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_data_management_renders_without_paper_profile(tmp_path,monkeypatch):
    monkeypatch.setenv("QUANTEDGE_WORKSPACE_DB",str(tmp_path/"workspace.sqlite"))
    monkeypatch.setenv("PAPER_DB_PATH",str(tmp_path/"no-paper.sqlite"))
    app=AppTest.from_string(
        "from stockmarket.workspace.data_management import data_management_page\n"
        "data_management_page()\n",default_timeout=25).run()
    assert not app.exception
    assert any("Data Management" in x.value for x in app.title)


def test_new_portability_is_reachable_and_worker_preserved():
    app=Path("src/stockmarket/ui/app.py").read_text()
    assert "data_management_page" in app
    assert Path("workspace_worker.py").is_file()
    assert Path("app.py").is_file()
