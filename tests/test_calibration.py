import numpy as np
import pandas as pd

from stockmarket.calibration import fit_probability_calibrator
from stockmarket.features import build_features
from stockmarket.modeling import train_model
from stockmarket.signals import make_signal


def test_probability_calibrator_maps_stronger_scores_to_higher_probability() -> None:
    scores = np.array([-0.04, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05])
    labels = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1], dtype=float)
    calibrator = fit_probability_calibrator(scores, labels)
    probabilities = calibrator.predict(np.array([-0.03, 0.04]))
    assert 0.0 <= probabilities[0] < probabilities[1] <= 1.0


def test_trained_model_exposes_calibrated_probability() -> None:
    index = pd.date_range("2026-01-01", periods=260, freq="h")
    x = np.arange(len(index), dtype=float)
    close = 100 + 0.03 * x + 3.0 * np.sin(x / 4.0) + 1.5 * np.sin(x / 11.0)
    bars = pd.DataFrame(
        {"Open": close - 0.2, "High": close + 0.9, "Low": close - 1.0, "Close": close, "Volume": 1_000_000 + x * 1_000},
        index=index,
    )
    features = build_features(bars, horizon=6, include_target=True, round_trip_cost=0.002)
    model = train_model(features, purge=6)
    probabilities = model.predict_probability(features.tail(5))
    assert model.calibrator is not None
    assert "brier_score" in model.metrics
    assert np.all((probabilities >= 0.0) & (probabilities <= 1.0))


def test_signal_confidence_uses_calibrated_probability_when_available() -> None:
    signal = make_signal(0.02, buy_threshold=0.005, sell_threshold=-0.005, round_trip_cost=0.003, calibrated_probability=0.78)
    assert signal.action == "Buy"
    assert signal.confidence == 0.78
    assert signal.probability_profitable == 0.78
