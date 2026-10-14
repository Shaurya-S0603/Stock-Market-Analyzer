"""Forward-only isolated strategy account with deterministic, atomic, idempotent fills."""
import numpy as np
import pandas as pd
import pytest

from stockmarket.workspace import WorkspaceDB
from stockmarket.workspace.strategy_repository import StrategyRepository
from stockmarket.workspace.strategy_paper import PaperStrategyRepository


def cache(db, closes):
    arr=np.asarray(closes,dtype=float)
    frame=pd.DataFrame({
        "open":arr,"high":arr+2,"low":arr-2,"close":arr,
        "volume":np.full(len(arr),1000.)
    },index=pd.date_range("2026-01-01",periods=len(arr),freq="d",tz="UTC"))
    db.save_candles("MSFT","1d",frame,provider="fixture")


def setup(tmp_path):
    file=tmp_path/"simulation.db"
    db=WorkspaceDB(str(file))
    cache(db,[100.,100.,100.,100.,100.,100.])
    s=StrategyRepository(db).save({
        "name":"Research-only SMA","symbol":"MSFT","timeframe":"1d",
        "entry":{"rules":[{"type":"price_above_sma","period":2}]},
        "exit":{"rules":[{"type":"rsi_threshold","period":2,
                           "direction":"above","threshold":100.}]},
        "risk":{"sizing":"fixed_quantity","value":3.,
                "stop_loss_pct":None,"take_profit_pct":None},
        "costs":{"commission_fixed":1.,"commission_pct":0., "slippage_pct":0.},
    })
    paper=PaperStrategyRepository(db)
    account=paper.create(s["id"],starting_cash=1000.)
    return file,db,paper,account


def test_activation_does_not_backfill_and_only_confirmed_bars_fill(tmp_path):
    file,db,paper,account=setup(tmp_path)
    assert paper.cycle(account)["status"]=="disabled"
    paper.set_enabled(account,True)
    assert paper.cycle(account)["status"]=="unchanged"
    # New provisional bar cannot be read as completed.
    cache(db,[100.,100.,100.,100.,100.,100.,105.])
    assert paper.cycle(account)["status"]=="unchanged"
    # The 105 bar now completed, produces an entry signal.
    cache(db,[100.,100.,100.,100.,100.,100.,105.,106.])
    assert paper.cycle(account)["bars"]==1
    assert paper.summary(account)["shares"]==0
    # Next bar confirms the 106 open; buy at its opening, after prior signal.
    cache(db,[100.,100.,100.,100.,100.,100.,105.,106.,107.])
    outcome=paper.cycle(account)
    assert outcome["fills"]==1
    summary=paper.summary(account)
    assert summary["shares"]==3
    assert summary["cash"]==pytest.approx(1000-3*106-1)
    assert paper.cycle(account)["status"]=="unchanged"
    restarted=PaperStrategyRepository(WorkspaceDB(str(file)))
    assert restarted.summary(account)["shares"]==3
    assert len(restarted.list_fills(account))==1
    assert len(restarted.list_decisions(account))==2
    assert not (tmp_path/"paper_trading.db").exists()


def test_pause_resume_does_not_generate_historical_entries(tmp_path):
    _,db,paper,account=setup(tmp_path)
    paper.set_enabled(account,True)
    paper.set_enabled(account,False)
    cache(db,[100.,100.,100.,100.,100.,100.,105.,106.,107.])
    assert paper.cycle(account)["status"]=="disabled"
    paper.set_enabled(account,True)
    assert paper.cycle(account)["status"]=="unchanged"
    assert paper.summary(account)["shares"]==0


def test_checkpoint_revisions_are_rejected(tmp_path):
    _,db,paper,account=setup(tmp_path)
    paper.set_enabled(account,True)
    cache(db,[100.,100.,100.,100.,111.,100.,105.])
    with pytest.raises(ValueError,match="checkpoint"):
        paper.cycle(account)


def test_multiple_accounts_do_not_share_cash_and_disabled_stays_unchanged(tmp_path):
    _,db,paper,first=setup(tmp_path)
    strategy_id=StrategyRepository(db).list_strategies()[0]["id"]
    second=paper.create(strategy_id,starting_cash=2000.)
    assert paper.summary(first)["cash"]==1000
    assert paper.summary(second)["cash"]==2000
    paper.set_enabled(first,True)
    cache(db,[100.,100.,100.,100.,100.,100.,105.,106.,107.])
    paper.cycle_all()
    assert paper.summary(first)["shares"]==3
    assert paper.summary(second)["shares"]==0
    assert not paper.summary(second)["enabled"]
