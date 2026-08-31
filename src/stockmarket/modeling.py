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
    momentum_weight: float = 0.30

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        linear = linear_prediction(features, self)
        momentum = momentum_prediction(features[self.feature_columns])
        return (1.0 - self.momentum_weight) * linear + self.momentum_weight * momentum


def _validate_training_frame(feature_frame: pd.DataFrame, minimum_rows: int = 20) -> None:
    missing = set(FEATURE_COLUMNS + ["target_return"]).difference(feature_frame.columns)
    if missing: raise ValueError(f"Training data is missing columns: {', '.join(sorted(missing))}")
    if len(feature_frame) < minimum_rows: raise ValueError(f"At least {minimum_rows} feature rows are required for training")
    values = feature_frame[FEATURE_COLUMNS + ["target_return"]].to_numpy(dtype=float)
    if not np.isfinite(values).all(): raise ValueError("Training data contains non-finite values")


def _fit_ridge(x: pd.DataFrame, y: pd.Series, ridge_penalty: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values=x.to_numpy(dtype=float); mean=values.mean(axis=0); scale=values.std(axis=0); scale[scale==0.0]=1.0
    x_std=(values-mean)/scale; design=np.c_[np.ones(len(x_std)),x_std]; target=y.to_numpy(dtype=float)
    penalty=ridge_penalty*np.eye(design.shape[1]); penalty[0,0]=0.0
    coefficients=np.linalg.solve(design.T@design+penalty,design.T@target)
    return coefficients,mean,scale


def momentum_prediction(features: pd.DataFrame) -> np.ndarray:
    missing={f"close_lag_{lag}" for lag in range(1,5)}.difference(features.columns)
    if missing: raise ValueError(f"Momentum features are missing columns: {', '.join(sorted(missing))}")
    lag_1=features["close_lag_1"].to_numpy(dtype=float); lag_2=features["close_lag_2"].to_numpy(dtype=float); lag_3=features["close_lag_3"].to_numpy(dtype=float); lag_4=features["close_lag_4"].to_numpy(dtype=float)
    return ((lag_1/lag_2-1.0)+(lag_2/lag_3-1.0)+(lag_3/lag_4-1.0))/3.0


def linear_prediction(features: pd.DataFrame, model: ModelResult) -> np.ndarray:
    x=features[model.feature_columns].to_numpy(dtype=float); x_std=(x-model.mean)/model.scale
    return np.c_[np.ones(len(x_std)),x_std]@model.coefficients


def evaluate_predictions(y_true: pd.Series, prediction: np.ndarray) -> dict[str,float]:
    actual=y_true.to_numpy(dtype=float); predicted=np.asarray(prediction,dtype=float)
    if len(actual)!=len(predicted) or len(actual)==0: raise ValueError("Actual and predicted returns must have the same non-zero length")
    residual=actual-predicted; strategy_returns=np.where(predicted>0.0,actual,0.0)
    return {"rmse":float(np.sqrt(np.mean(residual**2))),"mae":float(np.mean(np.abs(residual))),"directional_accuracy":float(np.mean(np.sign(actual)==np.sign(predicted))),"strategy_return":float(np.prod(1.0+strategy_returns)-1.0)}


def fit_model(feature_frame: pd.DataFrame, ridge_penalty: float=1e-3, momentum_weight: float=0.30) -> ModelResult:
    _validate_training_frame(feature_frame)
    if ridge_penalty<0: raise ValueError("ridge_penalty must be non-negative")
    if not 0.0<=momentum_weight<=1.0: raise ValueError("momentum_weight must be between 0 and 1")
    coefficients,mean,scale=_fit_ridge(feature_frame[FEATURE_COLUMNS],feature_frame["target_return"],ridge_penalty)
    return ModelResult(coefficients,mean,scale,ridge_penalty,{},list(FEATURE_COLUMNS),momentum_weight)


def train_model(feature_frame: pd.DataFrame,test_fraction: float=0.2,random_state: int=42,purge: int=1) -> ModelResult:
    _=random_state
    if not 0<test_fraction<1: raise ValueError("test_fraction must be between 0 and 1")
    if purge<0: raise ValueError("purge must be non-negative")
    _validate_training_frame(feature_frame,minimum_rows=40)
    train_end=int(len(feature_frame)*(1.0-test_fraction)); test_start=train_end+purge
    if train_end<20 or len(feature_frame)-test_start<5: raise ValueError("Training, purge, and test windows are too small")
    train_frame=feature_frame.iloc[:train_end]; test_frame=feature_frame.iloc[test_start:]
    validation_model=fit_model(train_frame); prediction=validation_model.predict(test_frame); metrics=evaluate_predictions(test_frame["target_return"],prediction)
    metrics["baseline_rmse"]=evaluate_predictions(test_frame["target_return"],np.zeros(len(test_frame),dtype=float))["rmse"]; metrics["holdout_rows"]=float(len(test_frame)); metrics["purge_rows"]=float(purge)
    final_model=fit_model(feature_frame); final_model.metrics=metrics
    return final_model


def walk_forward_scores(feature_frame: pd.DataFrame,splits: int=3,horizon: int=1)->list[dict[str,float]]:
    from .validation import walk_forward_scores as _walk_forward_scores
    return _walk_forward_scores(feature_frame,splits=splits,purge=horizon)
