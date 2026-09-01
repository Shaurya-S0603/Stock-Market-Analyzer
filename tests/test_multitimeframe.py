import numpy as np
import pandas as pd

from stockmarket.features import build_features
from stockmarket.modeling import fit_model
from stockmarket.multitimeframe import DAILY_CONTEXT_COLUMNS, build_daily_context, enrich_with_daily_context


def _bars(index: pd.DatetimeIndex, base: float = 100.0) -> pd.DataFrame:
    close = base + np.linspace(0, 20, len(index)) + np.sin(np.arange(len(index)) / 4)
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 0.8,
            "Low": close - 0.9,
            "Close": close,
            "Volume": 1_000_000 + np.arange(len(index)) * 1_000,
        },
        index=index,
    )


def test_daily_context_is_shifted_before_intraday_alignment() -> None:
    daily_index = pd.date_range("2026-01-01", periods=90, freq="D")
    daily = _bars(daily_index)
    context = build_daily_context(daily)

    expected_prior_return = daily["Close"].pct_change().iloc[59]
    assert context.loc[daily_index[60], "daily_return_1"] == expected_prior_return

    hourly_index = pd.date_range("2026-03-02 10:00", periods=7, freq="h")
    hourly = _bars(hourly_index, base=140)
    tactical = build_features(pd.concat([_bars(pd.date_range("2026-02-20", periods=80, freq="h"), base=120), hourly]), horizon=2)
    enriched = enrich_with_daily_context(tactical, daily)
    assert set(DAILY_CONTEXT_COLUMNS).issubset(enriched.columns)
    assert enriched.index.max() <= tactical.index.max()


def test_ridge_automatically_uses_dual_timeframe_numeric_features() -> None:
    index = pd.date_range("2026-01-01", periods=180, freq="h")
    features = build_features(_bars(index), horizon=3)
    for offset, column in enumerate(DAILY_CONTEXT_COLUMNS, start=1):
        features[column] = np.linspace(0.001 * offset, 0.01 * offset, len(features))
    model = fit_model(features)
    assert set(DAILY_CONTEXT_COLUMNS).issubset(model.feature_columns)
    assert len(model.predict(features.tail(3))) == 3
