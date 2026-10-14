"""Standalone one-cycle worker for Phase 4 cached alerts and simulated accounts.

Run manually: python workspace_worker.py
Optional online historical refresh: python workspace_worker.py --refresh
A scheduler may invoke this process periodically. It is never a brokerage client.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parent/"src"))
from stockmarket.workspace import WorkspaceDB
from stockmarket.workspace.alerts import AlertRepository
from stockmarket.workspace.strategy_paper import PaperStrategyRepository
from stockmarket.workspace.market_data import MarketDataService, MarketDataError


def run_once(db_path: str | None = None, *, refresh: bool = False) -> dict:
    db=WorkspaceDB(db_path)
    alerts=AlertRepository(db)
    paper=PaperStrategyRepository(db)
    updated=[]
    warnings=[]
    if refresh:
        observations=set()
        for a in alerts.list_rules():
            if a["enabled"]:
                d=a["definition"]
                observations.add((d["symbol"],d["interval"]))
        for a in paper.list_accounts():
            if a["enabled"]:
                observations.add((a["symbol"],a["interval"]))
        service=MarketDataService(db)
        intervals={"1m":"5d","5m":"30d","15m":"30d","1h":"60d",
                   "1d":"6mo","1wk":"2y","1mo":"5y"}
        for symbol,interval in sorted(observations):
            try:
                outcome=service.history(symbol,period=intervals[interval],
                                        interval=interval,refresh=True)
                if outcome.origin == "provider":
                    updated.append(f"{symbol}/{interval}")
                else:
                    warnings.append(f"{symbol}/{interval}: {outcome.warning}")
            except (MarketDataError,ValueError) as exc:
                warnings.append(f"{symbol}/{interval}: {exc}")
    errors=[]
    completed=[]
    for acct in paper.list_accounts():
        if acct["enabled"]:
            try:
                completed.append({"id":acct["id"]} | paper.cycle(acct["id"]))
            except (ValueError,RuntimeError) as exc:
                errors.append(f"paper #{acct['id']}: {exc}")
    try:
        alerts_summary=alerts.evaluate()
    except (ValueError,RuntimeError) as exc:
        alerts_summary={"new_events":0,"bars_examined":0}
        errors.append(f"alerts: {exc}")
    return {"refreshed":updated,"warnings":warnings,"paper_cycles":completed,
            "alerts":alerts_summary,"errors":errors}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Local cached research and paper-only simulation worker")
    parser.add_argument("--refresh",action="store_true",
                        help="Explicitly retrieve historical Yahoo candles before evaluating")
    parser.add_argument("--db",default=os.getenv("QUANTEDGE_WORKSPACE_DB",".data/workspace.db"))
    args=parser.parse_args()
    import json
    report=run_once(args.db,refresh=args.refresh)
    print(json.dumps(report,indent=2))
    if report["errors"]:
        sys.exit(1)
