from types import SimpleNamespace

from stockmarket.services.ai_trader import AITraderConfig, TraderMode
from stockmarket.services.opportunity import RankedOpportunity
from stockmarket.services.portfolio_cycle import PortfolioResearchCycle, PortfolioSignalState
from stockmarket.services.portfolio_optimizer import PortfolioOptimizer
from stockmarket.services.risk import RiskLimits
from stockmarket.trading import PaperPortfolio


def _state(symbol: str, edge: float, confidence: float, target_weight: float, volatility: float = 0.01):
    analysis = SimpleNamespace(
        price=100.0,
        live_features=SimpleNamespace(iloc=SimpleNamespace(__getitem__=lambda self, key: None)),
    )
    # Use a tiny dataframe-like shim only for the latest-row lookup used by the optimizer.
    import pandas as pd
    analysis.live_features = pd.DataFrame([{"context_volatility_20": volatility, "regime_high_volatility": 0.0}])
    return PortfolioSignalState(symbol, analysis, True, "pass", target_weight)


def test_optimizer_prioritizes_higher_risk_adjusted_edge_and_respects_sleeves() -> None:
    cycle = PortfolioResearchCycle(
        states={
            "AAA": _state("AAA", 0.02, 0.9, 20.0, 0.01),
            "BBB": _state("BBB", 0.01, 0.8, 10.0, 0.02),
        },
        unavailable={},
    )
    ranked = [
        RankedOpportunity(1, "AAA", True, "Buy", 0.9, 0.025, 0.02, True, 20.0, "eligible"),
        RankedOpportunity(2, "BBB", True, "Buy", 0.8, 0.015, 0.01, True, 10.0, "eligible"),
    ]
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    config = AITraderConfig(
        TraderMode.OBSERVE,
        min_confidence=0.6,
        allocation_pct=15.0,
        risk_limits=RiskLimits(max_position_pct=20, max_portfolio_exposure_pct=40, max_open_positions=5, max_daily_trades=10, max_daily_loss_pct=3, volatility_target_pct=1.5),
    )
    optimized = PortfolioOptimizer().optimize(cycle, ranked, portfolio, {"AAA": 100, "BBB": 100}, config)
    by_symbol = {item.symbol: item for item in optimized}
    assert by_symbol["AAA"].score > by_symbol["BBB"].score
    assert by_symbol["AAA"].target_entry_pct >= by_symbol["BBB"].target_entry_pct
    assert by_symbol["AAA"].target_entry_pct <= 20.0
    assert by_symbol["BBB"].target_entry_pct <= 10.0
