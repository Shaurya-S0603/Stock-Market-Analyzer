from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DriftReport:
    status: str
    score: float
    reasons: list[str]
    max_feature_z: float
    rmse_ratio: float
    directional_accuracy_drop: float
    brier_delta: float

    @property
    def drifted(self) -> bool:
        return self.status == "DRIFT"


def detect_experiment_drift(
    current: dict,
    baseline: dict,
    *,
    feature_z_threshold: float = 1.5,
    rmse_ratio_threshold: float = 1.25,
    directional_drop_threshold: float = 0.08,
    brier_delta_threshold: float = 0.05,
) -> DriftReport:
    current_metrics = current.get("metrics", {}) or {}
    baseline_metrics = baseline.get("metrics", {}) or {}
    current_stats = current.get("feature_stats", {}) or {}
    baseline_stats = baseline.get("feature_stats", {}) or {}

    feature_z_values: list[float] = []
    for feature, current_stat in current_stats.items():
        base_stat = baseline_stats.get(feature)
        if not base_stat:
            continue
        current_mean = float(current_stat.get("mean", 0.0) or 0.0)
        base_mean = float(base_stat.get("mean", 0.0) or 0.0)
        base_std = max(abs(float(base_stat.get("std", 0.0) or 0.0)), 1e-9)
        value = abs(current_mean - base_mean) / base_std
        if math.isfinite(value):
            feature_z_values.append(value)
    max_feature_z = max(feature_z_values, default=0.0)

    current_rmse = float(current_metrics.get("rmse", 0.0) or 0.0)
    baseline_rmse = float(baseline_metrics.get("rmse", 0.0) or 0.0)
    rmse_ratio = current_rmse / baseline_rmse if baseline_rmse > 0 else 1.0

    current_direction = float(current_metrics.get("directional_accuracy", 0.0) or 0.0)
    baseline_direction = float(baseline_metrics.get("directional_accuracy", 0.0) or 0.0)
    directional_drop = max(baseline_direction - current_direction, 0.0)

    current_brier = float(current_metrics.get("brier_score", 0.0) or 0.0)
    baseline_brier = float(baseline_metrics.get("brier_score", 0.0) or 0.0)
    brier_delta = max(current_brier - baseline_brier, 0.0) if baseline_brier > 0 else 0.0

    reasons: list[str] = []
    components: list[float] = []
    if max_feature_z > feature_z_threshold:
        reasons.append(f"Feature distribution shift reached {max_feature_z:.2f} baseline standard deviations.")
        components.append(max_feature_z / feature_z_threshold)
    if rmse_ratio > rmse_ratio_threshold:
        reasons.append(f"Holdout RMSE worsened to {rmse_ratio:.2f}x the baseline experiment.")
        components.append(rmse_ratio / rmse_ratio_threshold)
    if directional_drop > directional_drop_threshold:
        reasons.append(f"Directional accuracy fell by {directional_drop:.1%}.")
        components.append(directional_drop / directional_drop_threshold)
    if brier_delta > brier_delta_threshold:
        reasons.append(f"Probability calibration Brier score worsened by {brier_delta:.3f}.")
        components.append(brier_delta / brier_delta_threshold)

    score = max(components, default=0.0)
    return DriftReport(
        "DRIFT" if reasons else "STABLE",
        float(score),
        reasons or ["No configured drift threshold was breached."],
        float(max_feature_z),
        float(rmse_ratio),
        float(directional_drop),
        float(brier_delta),
    )
