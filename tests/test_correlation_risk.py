import numpy as np
import pandas as pd

from stockmarket.services.correlation import build_return_correlation_matrix, candidate_portfolio_correlation
from stockmarket.services.portfolio_cycle import PortfolioResearchCycle, PortfolioSignalState
from stockmarket.services.risk import RiskEngine, RiskLimits
from stockmarket.trading import PaperPortfolio


def _analysis(symbol: str, scale: float = 1.0, noise: float = 0.0):
    from types import SimpleNamespace

    index = pd.date_range("2026-01-01", periods=150, freq="h")
    x = np.arange(len(index), dtype=float)
    close = 100 + scale * (0.05 * x + 2.0 * np.sin(x / 7.0)) + noise * np.cos(x / 3.0)
    bars = pd.DataFrame(
        {"Open": close - 0.2, "High": close + 0.8, "Low": close - 0.8, "Close": close, "Volume": 1_000_000},
        index=index,
    )
    return SimpleNamespace(symbol=symbol, bars=bars)


def test_candidate_correlation_detects_near_duplicate_exposure() -> None:
    cycle = PortfolioResearchCycle(
        states={
            "AAA": PortfolioSignalState("AAA", _analysis("AAA", 1.0), True, "pass", 25.0),
            "BBB": PortfolioSignalState("BBB", _analysis("BBB", 1.01), True, "pass", 25.0),
        },
        unavailable={},
    )
    matrix = build_return_correlation_matrix(cycle)
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("AAA", "buy", 10, 100)
    correlation = candidate_portfolio_correlation("BBB", matrix, portfolio)
    assert correlation > 0.95


def test_correlation_matrix_skips_analyses_without_bar_history() -> None:
    from types import SimpleNamespace

    cycle = PortfolioResearchCycle(
        states={
            "AAA": PortfolioSignalState("AAA", SimpleNamespace(symbol="AAA"), True, "pass", 25.0),
            "BBB": PortfolioSignalState("BBB", _analysis("BBB"), True, "pass", 25.0),
        },
        unavailable={},
    )
    matrix = build_return_correlation_matrix(cycle)
    assert list(matrix.index) == ["BBB"]
    assert matrix.loc["BBB", "BBB"] == 1.0
    assert candidate_portfolio_correlation("AAA", matrix, PaperPortfolio(10_000, 0, 0)) == 0.0


def test_risk_engine_rejects_candidate_over_correlation_limit() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("AAA", "buy", 10, 100)
    limits = RiskLimits(
        max_position_pct=20,
        max_portfolio_exposure_pct=60,
        max_open_positions=6,
        max_daily_trades=20,
        max_daily_loss_pct=5,
        volatility_target_pct=1.5,
        max_pairwise_correlation=0.80,
    )
    assessment = RiskEngine().assess_entry(
        "BBB", 100, 0.8, 0.01, portfolio, {"AAA": 100, "BBB": 100}, [], 10, limits,
        correlation_to_portfolio=0.95,
    )
    assert not assessment.approved
    assert "Correlation" in assessment.reason


def test_moderate_correlation_reduces_paper_position_size() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    limits = RiskLimits(max_position_pct=30, max_portfolio_exposure_pct=80, max_open_positions=6, max_daily_trades=20, max_daily_loss_pct=5, volatility_target_pct=2)
    independent = RiskEngine().assess_entry("BBB", 100, 1.0, 0.01, portfolio, {"BBB": 100}, [], 20, limits, correlation_to_portfolio=0.0)
    correlated = RiskEngine().assess_entry("BBB", 100, 1.0, 0.01, portfolio, {"BBB": 100}, [], 20, limits, correlation_to_portfolio=0.75)
    assert independent.approved and correlated.approved
    assert correlated.quantity < independent.quantity
    assert correlated.correlation_adjustment < 1.0
