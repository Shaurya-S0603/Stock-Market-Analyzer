"""New Streamlit page and local worker smoke tests (offline)."""
import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("name",["alert_center_page","strategy_paper_page"])
def test_pages_render_offline(name,tmp_path,monkeypatch):
    monkeypatch.setenv("QUANTEDGE_WORKSPACE_DB",str(tmp_path/"monitor.db"))
    script=f"from stockmarket.workspace.monitor_pages import {name}\n{name}()\n"
    app=AppTest.from_string(script,default_timeout=25).run()
    assert not app.exception


def test_cached_worker_runs_without_network_or_paper_profile(tmp_path):
    from workspace_worker import run_once
    result=run_once(str(tmp_path/"worker.db"),refresh=False)
    assert result["alerts"]["new_events"]==0
    assert result["paper_cycles"]==[]
    assert result["errors"]==[]
