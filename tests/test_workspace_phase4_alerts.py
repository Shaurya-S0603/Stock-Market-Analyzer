"""Alert crossings, deduplication, persistence and completed-bar exclusion."""
import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from stockmarket.workspace import WorkspaceDB
from stockmarket.workspace.alerts import AlertRepository, AlertDefinition


def store(db, closes):
    frame = pd.DataFrame({
        "open":closes, "high":np.asarray(closes)+2., "low":np.asarray(closes)-2.,
        "close":closes, "volume":np.full(len(closes),10000.)
    }, index=pd.date_range("2026-01-01", periods=len(closes), freq="D", tz="UTC"))
    db.save_candles("MSFT","1d",frame,provider="fixture")


def test_alert_does_not_replay_old_cross_or_provisional_bar(tmp_path):
    path=tmp_path/"study.db"
    db=WorkspaceDB(str(path))
    store(db,[10.,11.,9.,9.,9.,9.])
    alert=AlertRepository(db)
    idx=alert.add("Cross 10",{"symbol":"MSFT","kind":"price_cross",
                              "direction":"above","threshold":10.})
    assert alert.evaluate()["new_events"] == 0
    # Last bar 11 is provisional, hence no alert yet.
    store(db,[10.,11.,9.,9.,9.,9.,11.])
    assert alert.evaluate()["new_events"] == 0
    # Adding a further bar confirms the prior 11 observation.
    store(db,[10.,11.,9.,9.,9.,9.,11.,12.])
    assert alert.evaluate()["new_events"] == 1
    assert alert.evaluate()["new_events"] == 0
    assert len(AlertRepository(WorkspaceDB(str(path))).list_events()) == 1
    assert alert.list_rules()[0]["id"]==idx


def test_alert_pause_reenable_and_validation(tmp_path):
    db=WorkspaceDB(str(tmp_path/"alerts.db"))
    store(db,[9.,9.,9.,9.,9.,9.])
    rep=AlertRepository(db)
    idx=rep.add("RSI",{"symbol":"MSFT","kind":"rsi_cross","threshold":60.,
                        "direction":"above"})
    rep.set_enabled(idx,False)
    store(db,[9.,9.,9.,9.,9.,9.,15.,16.])
    assert rep.evaluate()["new_events"]==0
    rep.set_enabled(idx,True)
    assert rep.evaluate()["new_events"]==0
    with pytest.raises(ValidationError):
        AlertDefinition(symbol="MSFT",kind="rsi_cross",threshold=101.)
    rep.delete(idx)
    assert rep.list_rules()==[]
