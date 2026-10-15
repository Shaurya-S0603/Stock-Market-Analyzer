"""Paper-only manual portfolio BUY/SELL integrity, restart and no overspending."""
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from stockmarket.workspace import WorkspaceDB
from stockmarket.workspace.manual_paper import ManualPaperRepository


def prepared(tmp_path):
    db=WorkspaceDB(str(tmp_path/"manual.db"))
    prices=np.full(8,100.,dtype=float)
    frame=pd.DataFrame({"open":prices,"high":prices+1,"low":prices-1,
                        "close":prices,"volume":np.full(8,1000.)},
                        index=pd.date_range("2026-01-01", periods=8, freq="D",tz="UTC"))
    db.save_candles("MSFT","1d",frame,provider="fixture")
    repo=ManualPaperRepository(db)
    return db,repo,repo.create("Practice","MSFT",1000.)


def test_cash_and_fees_reconcile_from_manual_buy_to_sell(tmp_path):
    db,repo,account=prepared(tmp_path)
    buy=repo.order(account,"buy",3,commission_fixed=2.,slippage_pct=1.)
    assert buy["price"] == pytest.approx(101.)
    assert repo.summary(account)["cash"]==pytest.approx(695.)
    assert repo.summary(account)["shares"]==3
    sell=repo.order(account,"sell",2,commission_fixed=1.,slippage_pct=1.)
    assert sell["price"]==pytest.approx(99.)
    assert sell["cash"]==pytest.approx(892.)
    assert sell["shares_held"]==1
    # Realized includes allocated entry fee and sell fee.
    assert sell["realized_pnl"]==pytest.approx(2*(99.-101.)-1.-2.*(2./3.))
    reopened=ManualPaperRepository(WorkspaceDB(db.path))
    assert reopened.summary(account)["shares"]==1
    assert len(reopened.list_orders(account))==2


def test_rejects_insufficient_cash_and_selling_unowned_shares(tmp_path):
    _,repo,account=prepared(tmp_path)
    with pytest.raises(ValueError,match="Insufficient"):
        repo.order(account,"buy",100)
    with pytest.raises(ValueError,match="Cannot sell"):
        repo.order(account,"sell",1)
    assert repo.summary(account)["cash"]==1000.
    assert repo.list_orders(account)==[]


def test_independent_paper_accounts_and_full_exit(tmp_path):
    _,repo,first=prepared(tmp_path)
    second=repo.create("Other","MSFT",500.)
    repo.order(first,"buy",3)
    repo.order(first,"sell",3)
    assert repo.summary(first)["shares"]==0
    assert repo.summary(first)["average_entry"]==0
    assert repo.summary(second)["cash"]==500.
    assert not repo.list_orders(second)


def test_manual_paper_page_renders_offline(tmp_path,monkeypatch):
    monkeypatch.setenv("QUANTEDGE_WORKSPACE_DB",str(tmp_path/"manual-page.db"))
    script="from stockmarket.workspace.manual_page import manual_paper_page\nmanual_paper_page()\n"
    app=AppTest.from_string(script,default_timeout=25).run()
    assert not app.exception
