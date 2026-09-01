from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ProbabilityCalibrator:
    intercept: float
    slope: float
    base_rate: float

    def predict(self, scores: np.ndarray) -> np.ndarray:
        values = np.asarray(scores, dtype=float)
        logits = np.clip(self.intercept + self.slope * values, -35.0, 35.0)
        return 1.0 / (1.0 + np.exp(-logits))


def fit_probability_calibrator(scores: np.ndarray, labels: np.ndarray, iterations: int = 50) -> ProbabilityCalibrator:
    x = np.asarray(scores, dtype=float).reshape(-1)
    y = np.asarray(labels, dtype=float).reshape(-1)
    if len(x) != len(y) or len(x) < 5:
        raise ValueError("Calibration needs at least five paired scores and labels")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Calibration data must be finite")
    if not np.isin(y, [0.0, 1.0]).all():
        raise ValueError("Calibration labels must be binary")

    base_rate = float(np.clip(y.mean(), 1e-4, 1.0 - 1e-4))
    intercept = float(np.log(base_rate / (1.0 - base_rate)))
    slope = 0.0
    if np.unique(y).size < 2 or np.std(x) < 1e-12:
        return ProbabilityCalibrator(intercept, slope, base_rate)

    scale = max(float(np.std(x)), 1e-9)
    z = x / scale
    beta = np.array([intercept, 0.0], dtype=float)
    design = np.c_[np.ones(len(z)), z]
    for _ in range(iterations):
        logits = np.clip(design @ beta, -35.0, 35.0)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        weights = np.clip(probabilities * (1.0 - probabilities), 1e-6, None)
        gradient = design.T @ (y - probabilities)
        hessian = design.T @ (weights[:, None] * design) + 1e-6 * np.eye(2)
        step = np.linalg.solve(hessian, gradient)
        beta += step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    return ProbabilityCalibrator(float(beta[0]), float(beta[1] / scale), base_rate)


def brier_score(probabilities: np.ndarray, labels: np.ndarray) -> float:
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(labels, dtype=float)
    if len(p) != len(y) or len(p) == 0:
        raise ValueError("Brier score requires paired non-empty arrays")
    return float(np.mean((np.clip(p, 0.0, 1.0) - y) ** 2))
