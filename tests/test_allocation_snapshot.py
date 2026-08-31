from stockmarket.services.allocation import build_allocation_snapshot
from stockmarket.trading import PaperPortfolio


def test_allocation_snapshot_reports_target_actual_and_cash() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("AAPL", "buy", 10, 100)
    rows = build_allocation_snapshot(
        portfolio,
        {"AAPL": 120.0, "MSFT": 200.0},
        {"AAPL": 30.0, "MSFT": 20.0},
        50.0,
    )
    by_symbol = {row.symbol: row for row in rows}
    assert set(by_symbol) == {"AAPL", "MSFT", "Cash"}
    assert by_symbol["AAPL"].target_pct == 30.0
    assert by_symbol["AAPL"].actual_pct > 0
    assert by_symbol["AAPL"].remaining_capacity > 0
    assert by_symbol["MSFT"].actual_pct == 0
    assert by_symbol["Cash"].is_cash
    assert by_symbol["Cash"].target_pct == 50.0
