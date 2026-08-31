from stockmarket.services.ai_trader import TradeDecision, TraderMode
from stockmarket.services.symbol_stats import build_symbol_strategy_stats
from stockmarket.storage import Store


def test_symbol_strategy_stats_separate_ticker_performance(tmp_path) -> None:
    store = Store(str(tmp_path / "paper.db"))
    aapl = TradeDecision("AAPL", "Buy", "BUY", 2, 100.0, 0.8, 0.02, 0.018, True, "test", True)
    msft = TradeDecision("MSFT", "Buy", "REJECT", 0, 100.0, 0.5, 0.01, 0.008, False, "test", False)
    store.add_ai_decision("c1", TraderMode.PAPER_AUTO.value, aapl)
    store.add_ai_decision("c2", TraderMode.OBSERVE.value, msft)
    store.add_order("AAPL", "sell", 2, 110, 0, realized_pnl=20, reason="ai_trader")
    store.add_order("AAPL", "sell", 1, 95, 0, realized_pnl=-5, reason="stop_loss")

    rows = build_symbol_strategy_stats(store)
    by_symbol = {row.symbol: row for row in rows}
    assert by_symbol["AAPL"].decisions == 1
    assert by_symbol["AAPL"].executed_decisions == 1
    assert by_symbol["AAPL"].closed_trades == 2
    assert by_symbol["AAPL"].win_rate == 0.5
    assert by_symbol["AAPL"].realized_pnl == 15
    assert by_symbol["AAPL"].expectancy == 7.5
    assert by_symbol["MSFT"].rejected_decisions == 1
    assert by_symbol["MSFT"].model_gate_pass_rate == 0.0
