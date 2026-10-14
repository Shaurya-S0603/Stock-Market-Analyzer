"""End-to-end offline strategy workflow: persist candle -> strategy -> backtest -> reopen."""
import numpy as np
import pandas as pd

from stockmarket.workspace import WorkspaceDB
from stockmarket.workspace.strategy_schema import parse_strategy
from stockmarket.workspace.strategy_backtest import run_backtest
from stockmarket.workspace.strategy_repository import StrategyRepository, compare_results


def test_saved_data_to_backtest_and_reopened_snapshot(tmp_path):
    filename = tmp_path/"workspace.db"
    db = WorkspaceDB(str(filename))
    series = 100 + np.arange(95) * 0.35
    frame = pd.DataFrame({
        "open":series, "high":series+1, "low":series-1,
        "close":series, "volume":np.full(95, 1500),
    }, index=pd.date_range("2026-01-01", periods=95, freq="d", tz="UTC"))
    db.save_candles("MSFT", "1d", frame, provider="offline-test")
    strategy = parse_strategy({
        "name":"Offline integration","symbol":"MSFT","timeframe":"1d",
        "entry":{"rules":[{"type":"price_above_sma","period":5}]},
        "exit":{"rules":[{"type":"rsi_threshold","period":2,
                          "direction":"above","threshold":100}]},
        "risk":{"sizing":"percent_of_equity","value":25,
                "stop_loss_pct":None,"take_profit_pct":None},
        "costs":{"commission_fixed":1.0,"commission_pct":0,"slippage_pct":0.05},
    })
    repo = StrategyRepository(db)
    saved = repo.save(strategy)
    results = run_backtest(db.load_candles("MSFT", "1d"), strategy, 10000)
    assert results["metrics"]["open_shares"] > 0
    assert results["orders"][0]["side"] == "buy"
    assert results["orders"][0]["status"] == "filled"
    assert results["metadata"]["provider"] == "offline-test"
    run_id = repo.save_backtest("Case A", results, saved["id"], saved["version"])
    recovered = StrategyRepository(WorkspaceDB(str(filename)))
    stored = recovered.load_backtest(run_id)["result"]
    assert stored == results
    assert stored["metadata"]["data_sha256"] == results["metadata"]["data_sha256"]
    frame_compare, warnings = compare_results([recovered.load_backtest(run_id)])
    assert len(frame_compare) == 1 and not warnings
    recovered.delete(saved["id"])
    assert recovered.load_backtest(run_id)["result"]["trades"] == results["trades"]
