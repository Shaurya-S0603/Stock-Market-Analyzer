from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stockmarket.services import assess_champion_challenger, run_monte_carlo_stress_test


def _row(model: str, rmse: float, direction: float, strategy_return: float, rank: float) -> dict:
    return {
        "model": model,
        "rmse": rmse,
        "mae": rmse * 0.8,
        "directional_accuracy": direction,
        "strategy_return": strategy_return,
        "complexity_rank": rank,
        "folds": 3.0,
    }


def test_champion_challenger_promotes_only_when_all_gates_pass() -> None:
    rows = [
        _row("zero_return", 0.020, 0.50, 0.00, 0),
        _row("ridge_momentum", 0.015, 0.55, 0.010, 5),
        _row("context_ensemble", 0.0144, 0.56, 0.014, 6),
        _row("regime_ensemble", 0.016, 0.58, 0.020, 7),
    ]
    decision = assess_champion_challenger(rows)
    assert decision.challenger == "context_ensemble"
    assert decision.recommendation == "PROMOTE_CHALLENGER"
    assert decision.rmse_improvement == pytest.approx(0.04)


def test_champion_challenger_keeps_production_when_direction_degrades() -> None:
    rows = [
        _row("ridge_momentum", 0.015, 0.60, 0.010, 5),
        _row("context_ensemble", 0.0140, 0.54, 0.020, 6),
    ]
    decision = assess_champion_challenger(rows)
    assert decision.recommendation == "KEEP_CHAMPION"
    assert decision.directional_delta < -0.02


def test_monte_carlo_stress_test_is_deterministic_and_finite() -> None:
    rng = np.random.default_rng(7)
    returns = rng.normal(0.001, 0.01, size=160)
    equity = pd.Series(10_000 * np.cumprod(1.0 + returns), name="equity")
    first = run_monte_carlo_stress_test(equity, simulations=500, horizon=80, block_size=5, seed=123)
    second = run_monte_carlo_stress_test(equity, simulations=500, horizon=80, block_size=5, seed=123)
    assert first == second
    assert 0.0 <= first.probability_of_loss <= 1.0
    assert first.p05_return_pct <= first.median_return_pct <= first.p95_return_pct
    assert first.p95_max_drawdown_pct <= 0.0


def test_monte_carlo_rejects_too_little_history() -> None:
    with pytest.raises(ValueError):
        run_monte_carlo_stress_test(pd.Series([100, 101, 102]), simulations=500)
