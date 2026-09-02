from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceDecision:
    champion: str
    challenger: str
    recommendation: str
    rmse_improvement: float
    directional_delta: float
    strategy_return_delta: float
    reason: str


def assess_champion_challenger(
    benchmark_rows: list[dict[str, float | str]],
    champion: str = "ridge_momentum",
    minimum_rmse_improvement: float = 0.02,
    maximum_directional_drop: float = 0.02,
) -> GovernanceDecision:
    """Compare the production candidate with the strongest non-baseline challenger.

    This is a governance recommendation only. It never changes the model used by the
    paper trader automatically.
    """
    if not benchmark_rows:
        raise ValueError("benchmark_rows cannot be empty")
    by_name = {str(row["model"]): row for row in benchmark_rows}
    if champion not in by_name:
        raise ValueError(f"Champion {champion} is missing from benchmark results")

    excluded = {"zero_return", "historical_mean", "momentum", champion}
    challengers = [row for row in benchmark_rows if str(row["model"]) not in excluded]
    if not challengers:
        return GovernanceDecision(
            champion,
            "none",
            "KEEP_CHAMPION",
            0.0,
            0.0,
            0.0,
            "No eligible challenger models were available.",
        )

    challenger_row = min(
        challengers,
        key=lambda row: (
            float(row["rmse"]),
            -float(row["directional_accuracy"]),
            float(row.get("complexity_rank", 999.0)),
        ),
    )
    champion_row = by_name[champion]
    champion_rmse = max(float(champion_row["rmse"]), 1e-12)
    challenger_rmse = float(challenger_row["rmse"])
    rmse_improvement = (champion_rmse - challenger_rmse) / champion_rmse
    directional_delta = float(challenger_row["directional_accuracy"]) - float(champion_row["directional_accuracy"])
    strategy_return_delta = float(challenger_row["strategy_return"]) - float(champion_row["strategy_return"])

    promote = (
        rmse_improvement >= minimum_rmse_improvement
        and directional_delta >= -maximum_directional_drop
        and strategy_return_delta > 0.0
        and float(challenger_row.get("folds", 0.0)) >= 3.0
    )
    challenger = str(challenger_row["model"])
    if promote:
        recommendation = "PROMOTE_CHALLENGER"
        reason = (
            f"{challenger} improved RMSE by {rmse_improvement:.1%}, changed directional accuracy by "
            f"{directional_delta:+.1%}, and improved mean strategy return by {strategy_return_delta:+.4f}. "
            "Promotion still requires an explicit code/configuration change."
        )
    else:
        recommendation = "KEEP_CHAMPION"
        reason = (
            f"{challenger} does not satisfy all promotion gates: RMSE improvement {rmse_improvement:.1%}, "
            f"directional delta {directional_delta:+.1%}, strategy-return delta {strategy_return_delta:+.4f}."
        )
    return GovernanceDecision(
        champion,
        challenger,
        recommendation,
        float(rmse_improvement),
        float(directional_delta),
        float(strategy_return_delta),
        reason,
    )
