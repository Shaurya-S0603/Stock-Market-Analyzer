"""Phase 5 restoration drill, WAL consistency and archive tamper tests."""
import hashlib
import json
import sqlite3
from io import BytesIO
import zipfile

import numpy as np
import pandas as pd
import pytest
from stockmarket.workspace import WorkspaceDB
from stockmarket.workspace.portability import make_archive, inspect_archive, stage_restore
from stockmarket.workspace.strategy_repository import StrategyRepository
from stockmarket.workspace.strategy_schema import example_strategy


def sample(db):
    db.add_to_watchlist(db.default_watchlist(),"MSFT")
    prices=100 + np.arange(40,dtype=float)
    frame=pd.DataFrame({"open":prices,"high":prices+2,"low":prices-2,
                       "close":prices,"volume":np.full(40,1000.)},
                       index=pd.date_range("2026-01-01",periods=40,freq="d",tz="UTC"))
    db.save_candles("MSFT","1d",frame,provider="offline")
    StrategyRepository(db).save(example_strategy())


def test_both_databases_backup_and_restore_without_overwrite(tmp_path):
    db=WorkspaceDB(str(tmp_path/"main.sqlite"));sample(db)
    with db.engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO workspace_watchlists(name,created_at) VALUES ('From WAL','now')")
    legacy=tmp_path/"old-paper.sqlite"
    with sqlite3.connect(str(legacy)) as conn:
        conn.execute("CREATE TABLE paper_balance(amount REAL)")
        conn.execute("INSERT INTO paper_balance VALUES (150)")
    archive=make_archive(db,str(legacy))
    assert set(inspect_archive(archive)["databases"])=={"workspace.sqlite","paper.sqlite"}
    dest=tmp_path/"recovered"
    info=stage_restore(archive,dest)
    assert info["requires_restart"]
    restored=WorkspaceDB(info["workspace_db"])
    assert len(restored.load_candles("MSFT","1d"))==40
    assert "From WAL" in {x["name"] for x in restored.list_watchlists()}
    assert StrategyRepository(restored).list_strategies()
    with sqlite3.connect(info["paper_db"]) as conn:
        assert conn.execute("SELECT amount FROM paper_balance").fetchone()==(150.0,)
    with pytest.raises(FileExistsError):
        stage_restore(archive,dest)
    assert db.path != info["workspace_db"]


def test_zip_traversal_checksum_and_invalid_db_rejected(tmp_path):
    db=WorkspaceDB(str(tmp_path/"source.sqlite"));sample(db)
    packed=make_archive(db)
    with zipfile.ZipFile(BytesIO(packed)) as z:
        members={n:z.read(n) for n in z.namelist()}
    members["workspace.sqlite"]+=b"tampered"
    b=BytesIO()
    with zipfile.ZipFile(b,"w") as z:
        for name,value in members.items():z.writestr(name,value)
    with pytest.raises(ValueError,match="checksum"):
        inspect_archive(b.getvalue())
    b=BytesIO()
    with zipfile.ZipFile(b,"w") as z:
        z.writestr("../bad.sqlite",b"bad")
        z.writestr("manifest.json",b"{}")
    with pytest.raises(ValueError,match="Unknown"):
        stage_restore(b.getvalue(),tmp_path/"should-not-exist")
    assert not (tmp_path/"should-not-exist").exists()
    fake=b"not a database"
    manifest={"format":"quantedge-local-backup/v1","databases":{
        "workspace.sqlite":{"size":len(fake),"sha256":hashlib.sha256(fake).hexdigest()}}}
    b=BytesIO()
    with zipfile.ZipFile(b,"w") as z:
        z.writestr("manifest.json",json.dumps(manifest))
        z.writestr("workspace.sqlite",fake)
    with pytest.raises(ValueError,match="SQLite"):
        inspect_archive(b.getvalue())
