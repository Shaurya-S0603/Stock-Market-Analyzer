from types import SimpleNamespace

from stockmarket.services.portfolio_cycle import PortfolioCycleService


def test_portfolio_cycle_evaluates_configured_symbols_in_order() -> None:
    analyses = {
        "AAPL": SimpleNamespace(symbol="AAPL"),
        "MSFT": SimpleNamespace(symbol="MSFT"),
    }

    class FakeAnalysisService:
        def analyze_watchlist(self, symbols, request):
            assert symbols == ["AAPL", "MSFT", "BAD"]
            return SimpleNamespace(available=analyses, unavailable={"BAD": "no data"})

        def benchmark_report(self, analysis):
            approved = analysis.symbol == "AAPL"
            return [], SimpleNamespace(approved=approved, reason=f"gate {analysis.symbol}")

    cycle = PortfolioCycleService(FakeAnalysisService()).run(
        ["AAPL", "MSFT", "BAD"],
        object(),
        {"AAPL": 35.0, "MSFT": 25.0},
    )
    assert list(cycle.states) == ["AAPL", "MSFT"]
    assert cycle.symbols_evaluated == 2
    assert cycle.model_gates == {"AAPL": True, "MSFT": False}
    assert cycle.states["AAPL"].target_weight == 35.0
    assert cycle.states["MSFT"].target_weight == 25.0
    assert cycle.unavailable == {"BAD": "no data"}
