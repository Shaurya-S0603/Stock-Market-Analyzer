from types import SimpleNamespace

import numpy as np
import pandas as pd

from stockmarket.services.drift import detect_experiment_drift
from stockmarket.services.experiment_registry import ExperimentRegistry


def test_drift_detector_flags_feature_and_metric_degradation() -> None:
    baseline = {
        "metrics": {"rmse": 0.010, "directional_accuracy": 0.58, "brier_score": 0.19},
        "feature_stats": {"context_return_6": {"mean": 0.0, "std": 0.01}},
    }
    current = {
        "metrics": {"rmse": 0.015, "directional_accuracy": 0.45, "brier_score": 0.27},
        "feature_stats": {"context_return_6": {"mean": 0.025, "std": 0.012}},
    }
    report = detect_experiment_drift(current, baseline)
    assert report.drifted
    assert report.max_feature_z > 1.5
    assert report.rmse_ratio > 1.25
    assert report.directional_accuracy_drop > 0.08


def test_drift_detector_keeps_similar_experiment_stable() -> None:
    baseline = {
        "metrics": {"rmse": 0.010, "directional_accuracy": 0.55, "brier_score": 0.20},
        "feature_stats": {"x": {"mean": 1.0, "std": 0.5}},
    }
    current = {
        "metrics": {"rmse": 0.0105, "directional_accuracy": 0.54, "brier_score": 0.205},
        "feature_stats": {"x": {"mean": 1.1, "std": 0.52}},
    }
    report = detect_experiment_drift(current, baseline)
    assert not report.drifted
    assert report.status == "STABLE"


def test_registry_persists_drift_event(tmp_path) -> None:
    registry = ExperimentRegistry(tmp_path / "paper.db")
    report = detect_experiment_drift(
        {"metrics": {"rmse": 0.02}, "feature_stats": {"x": {"mean": 3.0, "std": 1.0}}},
        {"metrics": {"rmse": 0.01}, "feature_stats": {"x": {"mean": 0.0, "std": 1.0}}},
    )
    registry.record_drift("exp-1", "MSFT", report)
    rows = registry.drift_events("MSFT")
    assert rows[0]["status"] == "DRIFT"
    assert rows[0]["details"]["max_feature_z"] == 3.0
