from stockmarket.services.risk import RiskEngine, RiskLimits
from stockmarket.trading import PaperPortfolio


def test_symbol_allocation_ceiling_caps_risk_sizing() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    limits = RiskLimits(
        max_position_pct=15,
        max_portfolio_exposure_pct=80,
        max_open_positions=8,
        max_daily_trades=20,
        max_daily_loss_pct=5,
        volatility_target_pct=2,
    )
    assessment = RiskEngine().assess_entry(
        "MSFT",
        100,
        1.0,
        0.01,
        portfolio,
        {"MSFT": 100},
        [],
        50,
        limits,
        symbol_allocation_pct=4.0,
    )
    assert assessment.approved
    assert assessment.quantity == 4
    assert assessment.symbol_cap_pct == 4.0
    assert assessment.allocation_value <= 400.0


def test_zero_symbol_allocation_blocks_entry() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    assessment = RiskEngine().assess_entry(
        "MSFT",
        100,
        0.9,
        0.01,
        portfolio,
        {"MSFT": 100},
        [],
        5,
        RiskLimits(),
        symbol_allocation_pct=0.0,
    )
    assert not assessment.approved
    assert "no enabled portfolio allocation" in assessment.reason.lower()
