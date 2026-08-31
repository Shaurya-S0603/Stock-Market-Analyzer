from stockmarket.services.attribution import build_portfolio_attribution
from stockmarket.storage import Store
from stockmarket.trading import PaperPortfolio


def test_portfolio_attribution_combines_realized_and_unrealized(tmp_path) -> None:
    store = Store(str(tmp_path / "paper.db"))
    store.add_order("AAPL", "sell", 1, 110, 1.0, realized_pnl=9.0, reason="ai_trader")
    store.add_order("MSFT", "sell", 1, 90, 1.0, realized_pnl=-11.0, reason="ai_trader")
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("NVDA", "buy", 2, 100)

    report = build_portfolio_attribution(store, portfolio, {"NVDA": 120.0})
    by_symbol = {row.symbol: row for row in report.symbols}
    assert report.realized_pnl == -2.0
    assert report.unrealized_pnl == 40.0
    assert report.total_pnl == 38.0
    assert report.orders == 2
    assert by_symbol["AAPL"].realized_pnl == 9.0
    assert by_symbol["MSFT"].realized_pnl == -11.0
    assert by_symbol["NVDA"].unrealized_pnl == 40.0
    assert round(sum(row.gross_contribution_pct for row in report.symbols), 6) == 100.0
