from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS


@dataclass
class ModelResult:
    coefficients: np.ndarray
    mean: np.ndarray
    scale: np.ndarray
    ridge_penalty: float
    metrics: dict[str, float]
    feature_columns: list[str]

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        x = features[self.feature_columns].to_numpy(dtype=float)
        x_std = (x - self.mean) / self.scale
        linear = np.c_[np.ones(len(x_std)), x_std] @ self.coefficients
        momentum = _momentum_prediction(features[self.feature_columns])
        return 0.7 * linear + 0.3 * momentum


def _rmse(y_true: pd.Series, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true.to_numpy(dtype=float) - y_pred) ** 2)))


def _mae(y_true: pd.Series, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true.to_numpy(dtype=float) - y_pred)))


def _fit_ridge(x: pd.DataFrame, y: pd.Series, ridge_penalty: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = x.to_numpy(dtype=float)
    mean = values.mean(axis=0)
    scale = values.std(axis=0)
    scale[scale == 0.0] = 1.0
    x_std = (values - mean) / scale
    design = np.c_[np.ones(len(x_std)), x_std]
    target = y.to_numpy(dtype=float)
    penalty = ridge_penalty * np.eye(design.shape[1])
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ target)
    return coefficients, mean, scale


def _momentum_prediction(features: pd.DataFrame) -> np.ndarray:
    lag_1 = features["close_lag_1"].to_numpy(dtype=float)
    lag_2 = features["close_lag_2"].to_numpy(dtype=float)
    lag_3 = features["close_lag_3"].to_numpy(dtype=float)
    lag_4 = features["close_lag_4"].to_numpy(dtype=float)
    ret_1 = lag_1 / lag_2 - 1.0
    ret_2 = lag_2 / lag_3 - 1.0
    ret_3 = lag_3 / lag_4 - 1.0
    return (ret_1 + ret_2 + ret_3) / 3.0


def train_model(feature_frame: pd.DataFrame, test_fraction: float = 0.2, random_state: int = 42) -> ModelResult:
    _ = random_state
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")
    if len(feature_frame) < 40:
        raise ValueError("At least 40 feature rows are required for training")
    split = int(len(feature_frame) * (1 - test_fraction))
    if split < 20 or len(feature_frame) - split < 5:
        raise ValueError("Training and test windows are too small")
    x_train = feature_frame[FEATURE_COLUMNS].iloc[:split]
    y_train = feature_frame["target_return"].iloc[:split]
    x_test = feature_frame[FEATURE_COLUMNS].iloc[split:]
    y_test = feature_frame["target_return"].iloc[split:]

    ridge_penalty = 1e-3
    coefficients, mean, scale = _fit_ridge(x_train, y_train, ridge_penalty)
    x_test_std = (x_test.to_numpy(dtype=float) - mean) / scale
    linear_prediction = np.c_[np.ones(len(x_test_std)), x_test_std] @ coefficients
    momentum_prediction = _momentum_prediction(x_test)
    prediction = 0.7 * linear_prediction + 0.3 * momentum_prediction
    baseline = np.zeros(len(y_test))
    metrics = {
        "rmse": _rmse(y_test, prediction),
        "mae": _mae(y_test, prediction),
        "directional_accuracy": float(np.mean(np.sign(y_test) == np.sign(prediction))),
        "baseline_rmse": _rmse(y_test, baseline),
        "strategy_return": float(np.sum(np.where(prediction > 0, y_test, 0.0))),
    }
    return ModelResult(coefficients, mean, scale, ridge_penalty, metrics, list(FEATURE_COLUMNS))


def walk_forward_scores(feature_frame: pd.DataFrame, splits: int = 3) -> list[dict[str, float]]:
    if len(feature_frame) < (splits + 1) * 12:
        raise ValueError("Not enough rows for walk-forward validation")
    scores = []
    x = feature_frame[FEATURE_COLUMNS]
    y = feature_frame["target_return"]
    fold_size = len(feature_frame) // (splits + 1)
    for fold in range(splits):
        train_end = fold_size * (fold + 1)
        test_start = train_end + 1
        test_end = min(test_start + fold_size, len(feature_frame))
        if test_end - test_start < 3:
            continue
        x_train = x.iloc[:train_end]
        y_train = y.iloc[:train_end]
        x_test = x.iloc[test_start:test_end]
        y_test = y.iloc[test_start:test_end]
        coefficients, mean, scale = _fit_ridge(x_train, y_train, ridge_penalty=1e-3)
        x_test_std = (x_test.to_numpy(dtype=float) - mean) / scale
        linear_prediction = np.c_[np.ones(len(x_test_std)), x_test_std] @ coefficients
        prediction = 0.7 * linear_prediction + 0.3 * _momentum_prediction(x_test)
        scores.append({
            "rmse": _rmse(y_test, prediction),
            "mae": _mae(y_test, prediction),
            "directional_accuracy": float(np.mean(np.sign(y_test) == np.sign(prediction))),
        })
    if not scores:
        raise ValueError("Unable to compute walk-forward scores with current data")
    return scores
