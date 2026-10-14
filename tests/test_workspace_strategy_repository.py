from stockmarket.workspace import WorkspaceDB
from stockmarket.workspace.strategy_schema import example_strategy
from stockmarket.workspace.strategy_repository import StrategyRepository, compare_results


def test_versioned_strategies_survive_restart_and_delete_preserves_backtests(tmp_path):
    file = tmp_path / "workspace.db"
    repo = StrategyRepository(WorkspaceDB(str(file)))
    one = repo.save(example_strategy())
    assert one["version"] == 1
    newer = example_strategy().model_copy(update={"description": "Improved hypothesis"})
    update = repo.save(newer, strategy_id=one["id"])
    assert update["version"] == 2
    second = StrategyRepository(WorkspaceDB(str(file)))
    assert second.list_versions(one["id"]) == [2, 1]
    assert second.load(one["id"], 1)["definition"]["description"] == ""
    assert second.load(one["id"])["definition"]["description"] == "Improved hypothesis"
    result = {
        "strategy_snapshot": newer.model_dump(mode="json"),
        "metadata": {"symbol": "MSFT", "timeframe": "1d", "from": "2026-01-01",
                     "to": "2026-08-01", "provider": "offline", "adjustment_mode": "raw",
                     "costs": {}, "data_sha256": "a"*64},
        "metrics": {"total_return_pct": 1}, "equity": [{"equity": 101}],
        "trades": [],
    }
    saved = second.save_backtest("Research comparison", result, one["id"], 2)
    second.delete(one["id"])
    restarted = StrategyRepository(WorkspaceDB(str(file)))
    assert restarted.list_strategies() == []
    assert restarted.load_backtest(saved)["result"]["strategy_snapshot"]["description"] == "Improved hypothesis"


def test_comparison_flags_mismatched_test_periods():
    base = {"id": 1, "name": "A",
            "result": {"strategy_snapshot": {"name": "Test"},
                       "metrics": {"total_return_pct": 1, "cagr_pct": None,
                                   "max_drawdown_pct": -1, "sharpe": None,
                                   "sortino": None, "win_rate_pct": None,
                                   "profit_factor": None, "trade_count": 0},
                       "metadata": {"symbol": "MSFT", "from": "2026-01-01",
                                    "to": "2026-06-01", "timeframe": "1d",
                                    "data_sha256": "a"*64, "provider": "test",
                                    "adjustment_mode": "raw", "costs": {}}}}
    other = {"id": 2, "name": "B",
             "result": {**base["result"], "metadata": {**base["result"]["metadata"], "to": "2026-07-01"}}}
    frame, warnings = compare_results([base, other])
    assert len(frame) == 2
    assert any("dates" in w for w in warnings)
