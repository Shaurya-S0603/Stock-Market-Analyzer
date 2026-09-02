from types import SimpleNamespace

import pandas as pd
import pytest

from stockmarket.benchmarks import assess_trading_evidence
from stockmarket.services.ai_trader import AITraderConfig, AITraderService, TraderMode, required_entry_confidence
from stockmarket.services.opportunity import OpportunityRanker
from stockmarket.services.portfolio_cycle import PortfolioResearchCycle, PortfolioSignalState
from stockmarket.services.risk import RiskLimits
from stockmarket.simulation_worker import _risk_config
from stockmarket.trading import PaperPortfolio


def _benchmark_rows(candidate_rmse: float, direction: float, strategy_return: float):
    return [
        {"model": "zero_return", "rmse": 0.0100, "directional_accuracy": 0.50, "strategy_return": 0.0},
        {"model": "historical_mean", "rmse": 0.0098, "directional_accuracy": 0.50, "strategy_return": 0.0},
        {"model": "momentum", "rmse": 0.0095, "directional_accuracy": 0.50, "strategy_return": 0.0},
        {"model": "ridge_momentum", "rmse": candidate_rmse, "directional_accuracy": direction, "strategy_return": strategy_return},
    ]


def test_graded_trading_evidence_allows_borderline_positive_model_at_reduced_size() -> None:
    gate = assess_trading_evidence(_benchmark_rows(0.0097, 0.49, 0.001))
    assert gate.approved
    assert gate.tier == "acceptable"
    assert gate.size_multiplier == pytest.approx(0.65)


def test_graded_trading_evidence_still_rejects_materially_weak_model() -> None:
    gate = assess_trading_evidence(_benchmark_rows(0.0110, 0.44, -0.001))
    assert not gate.approved
    assert gate.tier == "weak"
    assert gate.size_multiplier == 0.0


def test_edge_aware_confidence_relief_has_a_hard_floor() -> None:
    assert required_entry_confidence(0.58, 0.003, 0.003) == pytest.approx(0.58)
    assert required_entry_confidence(0.58, 0.006, 0.003) == pytest.approx(0.54)
    assert required_entry_confidence(0.65, 0.020, 0.003) == pytest.approx(0.55)
    assert required_entry_confidence(0.58, 1.0, 0.003) == pytest.approx(0.52)


def test_strong_edge_buy_below_old_65_percent_confidence_gets_nonzero_quantity() -> None:
    signal = SimpleNamespace(action="Buy", confidence=0.56, net_edge=0.006)
    analysis = SimpleNamespace(
        symbol="AAA",
        signal=signal,
        price=100.0,
        predicted_return=0.009,
        adaptive_buy_threshold=0.003,
        live_features=pd.DataFrame([{"volatility_10": 0.01}]),
    )
    portfolio = PaperPortfolio(10_000.0, commission_rate=0.0, slippage_rate=0.0)
    config = AITraderConfig(
        mode=TraderMode.OBSERVE,
        min_confidence=0.58,
        allocation_pct=7.5,
        risk_limits=RiskLimits(
            max_position_pct=12.0,
            max_portfolio_exposure_pct=70.0,
            max_open_positions=8,
            max_daily_trades=16,
            max_daily_loss_pct=3.0,
            volatility_target_pct=1.75,
            max_pairwise_correlation=0.92,
            correlation_penalty_floor=0.40,
        ),
    )
    decision = AITraderService().evaluate_symbol(
        analysis,
        True,
        portfolio,
        config,
        prices={"AAA": 100.0},
        orders=[],
    )
    assert decision.decision == "BUY"
    assert decision.quantity > 0


def test_ranker_uses_same_edge_adjusted_confidence_as_executor() -> None:
    signal = SimpleNamespace(action="Buy", confidence=0.56, net_edge=0.006)
    analysis = SimpleNamespace(
        signal=signal,
        predicted_return=0.009,
        adaptive_buy_threshold=0.003,
    )
    state = PortfolioSignalState("AAA", analysis, True, "acceptable", 20.0, "acceptable", 0.65)
    cycle = PortfolioResearchCycle(states={"AAA": state}, unavailable={})
    ranked = OpportunityRanker().rank(cycle, min_confidence=0.58)
    assert ranked[0].eligible
    assert ranked[0].required_confidence == pytest.approx(0.54)
    assert ranked[0].evidence_tier == "acceptable"


def test_balanced_worker_profile_is_return_seeking_but_keeps_daily_loss_limit(monkeypatch) -> None:
    monkeypatch.delenv("PAPER_MIN_CONFIDENCE", raising=False)
    monkeypatch.delenv("PAPER_ENTRY_ALLOCATION_PCT", raising=False)
    config = _risk_config("Balanced", TraderMode.PAPER_AUTO, 20.0)
    assert config.min_confidence == pytest.approx(0.58)
    assert config.risk_limits.max_portfolio_exposure_pct == pytest.approx(70.0)
    assert config.risk_limits.max_daily_loss_pct == pytest.approx(3.0)
