from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS
from .modeling import evaluate_predictions, fit_model, momentum_prediction
from .validation import purged_walk_forward_splits


@dataclass(frozen=True)
class ModelGate:
    candidate: str
    approved: bool
    reason: str
    rmse_improvement_vs_best_baseline: float
    directional_accuracy: float


def _core_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[[column for column in FEATURE_COLUMNS if column in frame.columns] + ["target_return"]]


def _regime_ensemble(train_frame: pd.DataFrame, test_frame: pd.DataFrame) -> np.ndarray:
    ridge = fit_model(train_frame, momentum_weight=0.0).predict(test_frame)
    momentum = momentum_prediction(test_frame)
    historical_mean = np.full(len(test_frame), float(train_frame["target_return"].mean()), dtype=float)
    trending = test_frame.get("regime_trending", pd.Series(0.0, index=test_frame.index)).to_numpy(dtype=float)
    high_vol = test_frame.get("regime_high_volatility", pd.Series(0.0, index=test_frame.index)).to_numpy(dtype=float)
    ridge_weight = 0.55 + 0.15 * high_vol
    momentum_weight = 0.25 + 0.15 * trending - 0.10 * high_vol
    mean_weight = np.clip(1.0 - ridge_weight - momentum_weight, 0.0, 1.0)
    total = ridge_weight + momentum_weight + mean_weight
    return (ridge * ridge_weight + momentum * momentum_weight + historical_mean * mean_weight) / total


def _candidate_predictions(name: str, train_frame: pd.DataFrame, test_frame: pd.DataFrame) -> np.ndarray:
    if name == "zero_return":
        return np.zeros(len(test_frame), dtype=float)
    if name == "historical_mean":
        return np.full(len(test_frame), float(train_frame["target_return"].mean()), dtype=float)
    if name == "momentum":
        return momentum_prediction(test_frame)
    if name == "ridge":
        return fit_model(train_frame, momentum_weight=0.0).predict(test_frame)
    if name == "ridge_momentum":
        return fit_model(train_frame, momentum_weight=0.30).predict(test_frame)
    if name == "ridge_core":
        return fit_model(_core_frame(train_frame), momentum_weight=0.0).predict(test_frame[FEATURE_COLUMNS])
    if name == "context_ensemble":
        ridge = fit_model(train_frame, momentum_weight=0.0).predict(test_frame)
        momentum = momentum_prediction(test_frame)
        mean = np.full(len(test_frame), float(train_frame["target_return"].mean()), dtype=float)
        return 0.65 * ridge + 0.25 * momentum + 0.10 * mean
    if name == "regime_ensemble":
        return _regime_ensemble(train_frame, test_frame)
    raise ValueError(f"Unknown benchmark candidate: {name}")


def _benchmark_candidates(
    feature_frame: pd.DataFrame,
    candidates: list[str],
    splits: int,
    purge: int,
) -> list[dict[str, float | str]]:
    folds = purged_walk_forward_splits(len(feature_frame), splits=splits, purge=purge)
    per_candidate = {name: [] for name in candidates}
    for fold in folds:
        train_frame = feature_frame.iloc[fold.train_start : fold.train_end]
        test_frame = feature_frame.iloc[fold.test_start : fold.test_end]
        actual = test_frame["target_return"]
        for name in candidates:
            per_candidate[name].append(evaluate_predictions(actual, _candidate_predictions(name, train_frame, test_frame)))
    rows: list[dict[str, float | str]] = []
    for complexity_rank, name in enumerate(candidates):
        metrics = per_candidate[name]
        rows.append(
            {
                "model": name,
                "complexity_rank": float(complexity_rank),
                "folds": float(len(metrics)),
                "rmse": float(np.mean([item["rmse"] for item in metrics])),
                "mae": float(np.mean([item["mae"] for item in metrics])),
                "directional_accuracy": float(np.mean([item["directional_accuracy"] for item in metrics])),
                "strategy_return": float(np.mean([item["strategy_return"] for item in metrics])),
            }
        )
    return rows


def benchmark_models(feature_frame: pd.DataFrame, splits: int = 3, purge: int = 1) -> list[dict[str, float | str]]:
    """Backward-compatible core benchmark ladder used by the production evidence gate."""
    return _benchmark_candidates(
        feature_frame,
        ["zero_return", "historical_mean", "momentum", "ridge", "ridge_momentum"],
        splits,
        purge,
    )


def ensemble_benchmark_models(feature_frame: pd.DataFrame, splits: int = 3, purge: int = 1) -> list[dict[str, float | str]]:
    """Extended challenger ladder. It does not silently replace the current production candidate."""
    return _benchmark_candidates(
        feature_frame,
        [
            "zero_return",
            "historical_mean",
            "momentum",
            "ridge_core",
            "ridge",
            "ridge_momentum",
            "context_ensemble",
            "regime_ensemble",
        ],
        splits,
        purge,
    )


def assess_model_gate(
    benchmark_rows: list[dict[str, float | str]],
    candidate: str = "ridge_momentum",
    minimum_directional_accuracy: float = 0.50,
    minimum_rmse_improvement: float = 0.0,
) -> ModelGate:
    by_name = {str(row["model"]): row for row in benchmark_rows}
    if candidate not in by_name:
        raise ValueError(f"Candidate {candidate} is missing from benchmark results")
    baseline_names = [name for name in ("zero_return", "historical_mean", "momentum") if name in by_name]
    if not baseline_names:
        raise ValueError("At least one simple benchmark is required")
    candidate_row = by_name[candidate]
    candidate_rmse = float(candidate_row["rmse"])
    best_baseline_rmse = min(float(by_name[name]["rmse"]) for name in baseline_names)
    improvement = (best_baseline_rmse - candidate_rmse) / max(best_baseline_rmse, 1e-12)
    directional_accuracy = float(candidate_row["directional_accuracy"])
    approved = improvement > minimum_rmse_improvement and directional_accuracy >= minimum_directional_accuracy
    if approved:
        reason = f"Candidate beat the best simple baseline RMSE by {improvement:.1%} and achieved {directional_accuracy:.1%} mean directional accuracy."
    elif improvement <= minimum_rmse_improvement:
        reason = f"Candidate did not beat the best simple baseline RMSE; relative improvement was {improvement:.1%}."
    else:
        reason = f"RMSE improved by {improvement:.1%}, but mean directional accuracy of {directional_accuracy:.1%} is below the {minimum_directional_accuracy:.0%} gate."
    return ModelGate(candidate, approved, reason, improvement, directional_accuracy)


def best_benchmark(benchmark_rows: list[dict[str, float | str]]) -> dict[str, float | str]:
    if not benchmark_rows:
        raise ValueError("Benchmark rows cannot be empty")
    return min(
        benchmark_rows,
        key=lambda row: (
            float(row["rmse"]),
            -float(row["directional_accuracy"]),
            float(row["complexity_rank"]),
        ),
    )
