from types import SimpleNamespace

from stockmarket.services import AITraderConfig, RiskLimits, TraderMode
from stockmarket.services.paper_strategy import PaperOnlyPortfolioStrategy
from stockmarket.services.portfolio import PortfolioService
from stockmarket.services.portfolio_cycle import PortfolioResearchCycle, PortfolioSignalState
from stockmarket.storage import Store
from stockmarket.trading import PaperPortfolio


def _state(symbol: str, edge: float, confidence: float, target: float):
    analysis = SimpleNamespace(
        symbol=symbol,
        price=100.0,
        predicted_return=edge + 0.002,
        signal=SimpleNamespace(action="Buy", confidence=confidence, net_edge=edge),
    )
    return PortfolioSignalState(symbol, analysis, True, "passed", target)


def test_paper_strategy_prioritizes_rank_before_lower_scored_entries(tmp_path) -> None:
    cycle = PortfolioResearchCycle(
        states={
            "AAPL": _state("AAPL", 0.010, 0.80, 30.0),
            "NVDA": _state("NVDA", 0.020, 0.90, 70.0),
        },
        unavailable={},
    )
    portfolio = PaperPortfolio(1_000, commission_rate=0, slippage_rate=0)
    service = PortfolioService(portfolio, Store(str(tmp_path / "paper.db")))
    config = AITraderConfig(
        TraderMode.PAPER_AUTO,
        min_confidence=0.65,
        allocation_pct=80.0,
        risk_limits=RiskLimits(
            max_position_pct=100,
            max_portfolio_exposure_pct=100,
            max_open_positions=5,
            max_daily_trades=10,
            max_daily_loss_pct=5,
            volatility_target_pct=5,
        ),
    )

    result = PaperOnlyPortfolioStrategy().run(cycle, service, config)
    assert result.ranked_opportunities[0].symbol == "NVDA"
    assert result.decisions[0].symbol == "NVDA"
    assert result.decisions[0].executed
    assert portfolio.positions["NVDA"].quantity > 0
    assert portfolio.positions["AAPL"].quantity > 0
    assert portfolio.positions["NVDA"].quantity > portfolio.positions["AAPL"].quantity


def test_observe_mode_never_changes_paper_positions(tmp_path) -> None:
    cycle = PortfolioResearchCycle(states={"AAPL": _state("AAPL", 0.02, 0.9, 80.0)}, unavailable={})
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    service = PortfolioService(portfolio, Store(str(tmp_path / "paper.db")))
    config = AITraderConfig(TraderMode.OBSERVE, min_confidence=0.65, allocation_pct=20.0)
    result = PaperOnlyPortfolioStrategy().run(cycle, service, config)
    assert result.decisions[0].decision == "BUY"
    assert not result.decisions[0].executed
    assert portfolio.positions.get("AAPL") is None
