"""OHLCV CSV fidelity, timezone and historical overwrite guards."""
import numpy as np
import pandas as pd
import pytest
from stockmarket.workspace import WorkspaceDB
from stockmarket.workspace.csv_io import export_history_csv,import_history_csv


def sample(db):
    p=100+np.arange(24,dtype=float)
    db.save_candles("MSFT","1d",pd.DataFrame({
        "open":p,"high":p+2,"low":p-2,"close":p,"volume":np.full(24,3000.)
    },index=pd.date_range("2026-01-01",periods=24,freq="D",tz="UTC")),provider="offline-test")


def test_round_trip_and_idempotence(tmp_path):
    source=WorkspaceDB(str(tmp_path/"one.db"));sample(source)
    payload=export_history_csv(source,"MSFT","1d")
    dest=WorkspaceDB(str(tmp_path/"two.db"))
    info=import_history_csv(dest,payload,symbol="MSFT",interval="1d")
    assert info["bars_imported"]==24 and info["provider"]=="offline-test"
    assert import_history_csv(dest,payload,symbol="MSFT",interval="1d")["bars_imported"]==24
    original=source.load_candles("MSFT","1d")
    copied=dest.load_candles("MSFT","1d")
    pd.testing.assert_index_equal(original.index,copied.index)
    np.testing.assert_allclose(original["close"],copied["close"])
    assert len(copied)==24


def test_rejects_ambiguous_or_inconsistent_market_data(tmp_path):
    db=WorkspaceDB(str(tmp_path/"bad.db"))
    with pytest.raises(ValueError,match="offset"):
        import_history_csv(db,b"timestamp,open,high,low,close,volume\n2026-01-01,10,11,9,10,100\n",symbol="MSFT",interval="1d")
    with pytest.raises(ValueError,match="Duplicate"):
        import_history_csv(db,b"timestamp,open,high,low,close,volume\n2026-01-01T00:00:00Z,10,11,9,10,100\n2026-01-01T00:00:00Z,10,11,9,10,100\n",symbol="MSFT",interval="1d")
    with pytest.raises(ValueError,match="Inconsistent"):
        import_history_csv(db,b"timestamp,open,high,low,close,volume\n2026-01-01T00:00:00Z,10,1,9,10,100\n",symbol="MSFT",interval="1d")
    assert db.cached_symbols()==[]


def test_existing_candles_cannot_be_silently_changed(tmp_path):
    db=WorkspaceDB(str(tmp_path/"prices.db"));sample(db)
    original=export_history_csv(db,"MSFT","1d").decode("utf-8")
    modified=original.replace(",100,102,98,100,3000",",100,120,98,100,3000",1)
    with pytest.raises(ValueError,match="revise"):
        import_history_csv(db,modified.encode(),symbol="MSFT",interval="1d")
    with pytest.raises(ValueError,match="different provider"):
        import_history_csv(db,original.replace("offline-test","other-test").encode(),symbol="MSFT",interval="1d")
