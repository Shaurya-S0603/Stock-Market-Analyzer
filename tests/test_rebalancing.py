from stockmarket.services.rebalancing import build_rebalance_plan
from stockmarket.trading import PaperPortfolio


def test_rebalance_plan_sells_overweight_before_buying_underweight() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("AAPL", "buy", 60, 100)
    plan = build_rebalance_plan(
        portfolio,
        {"AAPL": 100.0, "MSFT": 100.0},
        {"AAPL": 30.0, "MSFT": 30.0},
        40.0,
        tolerance_pct=1.0,
    )
    assert plan.instructions
    assert plan.instructions[0].side == "sell"
    assert plan.instructions[0].symbol == "AAPL"
    assert any(item.side == "buy" and item.symbol == "MSFT" for item in plan.instructions)
    assert plan.estimated_cash_after >= plan.target_cash_value


def test_rebalance_plan_is_empty_inside_tolerance() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    plan = build_rebalance_plan(
        portfolio,
        {"AAPL": 100.0},
        {"AAPL": 0.0},
        100.0,
        tolerance_pct=2.0,
    )
    assert plan.instructions == ()
