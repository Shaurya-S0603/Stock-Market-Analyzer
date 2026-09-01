from types import SimpleNamespace

import numpy as np
import pandas as pd

from stockmarket.services.experiment_registry import ExperimentRegistry


def _analysis():
    index = pd.date_range("2026-01-01", periods=50, freq="h")
    return SimpleNamespace(
        symbol="MSFT",
        training_features=pd.DataFrame({"x": np.arange(50)}, index=index),
        model=SimpleNamespace(
            coefficients=np.array([0.1, 0.2, -0.05]),
            feature_columns=["sma_5", "context_return_6"],
            ridge_penalty=0.001,
            momentum_weight=0.30,
            metrics={"rmse": 0.01, "directional_accuracy": 0.55},
        ),
        regime="bullish trend",
        adaptive_buy_threshold=0.004,
        adaptive_sell_threshold=-0.006,
    )


def _request():
    return SimpleNamespace(
        period="60d",
        interval="1h",
        horizon=6,
        context_period="6mo",
        context_interval="1d",
        benchmark_symbol="SPY",
        buy_threshold=0.005,
        sell_threshold=-0.005,
        round_trip_cost=0.003,
    )


def test_experiment_registry_persists_reproducible_model_metadata(tmp_path) -> None:
    registry = ExperimentRegistry(tmp_path / "paper.db")
    analysis = _analysis()
    first = registry.record(analysis, _request(), {"best_challenger": {"model": "regime_ensemble", "rmse": 0.009}})
    second = registry.record(analysis, _request(), {"best_challenger": {"model": "regime_ensemble", "rmse": 0.009}})
    rows = registry.recent("MSFT")
    assert first.experiment_id == second.experiment_id
    assert len(rows) == 1
    assert rows[0]["model_hash"] == first.model_hash
    assert rows[0]["parameters"]["interval"] == "1h"
    assert rows[0]["feature_columns"] == analysis.model.feature_columns
    assert rows[0]["benchmark"]["best_challenger"]["model"] == "regime_ensemble"
