"""Cloud-demo isolation, tutorial fixture and zero-network startup tests."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from stockmarket.workspace import WorkspaceDB
from stockmarket.workspace.strategy_repository import StrategyRepository
from stockmarket.workspace.tutorial import install_demo_example, synthetic_demo_bars


def test_synthetic_tutorial_has_valid_candles_and_no_network(tmp_path):
    db=WorkspaceDB(str(tmp_path/"example.sqlite"))
    report=install_demo_example(db)
    assert report=={"symbol":"QEDMO","bars":320}
    candles=db.load_candles("QEDMO","1d")
    assert len(candles)==320
    assert set(candles["provider"])=={"synthetic-tutorial"}
    assert (candles["high"] >= candles[["open","close"]].max(axis=1)).all()
    assert (candles["low"] <= candles[["open","close"]].min(axis=1)).all()
    install_demo_example(db)
    assert len(StrategyRepository(db).list_strategies())==1


def test_public_sessions_have_different_temporary_sqlite_paths(monkeypatch):
    monkeypatch.setenv("QUANTEDGE_PUBLIC_DEMO","1")
    monkeypatch.setenv("QUANTEDGE_WORKSPACE_DB","/tmp/must-not-be-shared.sqlite")
    script=("import streamlit as st\n"
            "from stockmarket.workspace.runtime import workspace_path\n"
            "st.caption(workspace_path())\n"
            "st.caption(workspace_path())\n")
    a=AppTest.from_string(script).run()
    b=AppTest.from_string(script).run()
    assert not a.exception and not b.exception
    assert a.caption[0].value==a.caption[1].value
    assert a.caption[0].value != b.caption[0].value
    assert "must-not-be-shared" not in a.caption[0].value
    assert "quantedge_public_demo" in a.caption[0].value


def test_local_mode_keeps_explicit_persistent_path(tmp_path, monkeypatch):
    monkeypatch.delenv("QUANTEDGE_PUBLIC_DEMO",raising=False)
    monkeypatch.setenv("QUANTEDGE_WORKSPACE_DB",str(tmp_path/"persistent.sqlite"))
    from stockmarket.workspace.runtime import workspace_path
    assert workspace_path()==str(tmp_path/"persistent.sqlite")


def test_tutorial_page_opens_with_empty_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTEDGE_PUBLIC_DEMO","1")
    monkeypatch.setenv("QUANTEDGE_WORKSPACE_DB",str(tmp_path/"unused.sqlite"))
    app=AppTest.from_string(
        "from stockmarket.workspace.tutorial import tutorial_page\n"
        "tutorial_page()\n",default_timeout=25).run()
    assert not app.exception
    assert any("Website Tutorial" in x.value for x in app.title)
