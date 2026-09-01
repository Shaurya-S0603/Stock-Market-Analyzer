import numpy as np
import pandas as pd

from stockmarket.context_features import TACTICAL_CONTEXT_COLUMNS, build_tactical_context, enrich_with_tactical_context
from stockmarket.features import build_features


def _bars(index: pd.DatetimeIndex, drift: float = 0.15) -> pd.DataFrame:
    close = 100 + np.arange(len(index)) * drift + np.sin(np.arange(len(index)) / 5)
    return pd.DataFrame(
        {
            "Open": close * 0.999,
            "High": close * 1.006,
            "Low": close * 0.994,
            "Close": close,
            "Volume": 1_000_000 + np.arange(len(index)) * 2_000,
        },
        index=index,
    )


def test_tactical_context_adds_market_relative_and_session_features() -> None:
    index = pd.date_range("2026-01-01 09:30", periods=180, freq="h")
    bars = _bars(index, drift=0.18)
    benchmark = _bars(index, drift=0.08)
    context = build_tactical_context(bars, benchmark).dropna(subset=TACTICAL_CONTEXT_COLUMNS)
    assert not context.empty
    assert context.iloc[-1]["context_relative_strength_6"] > 0
    assert -1.0 <= context.iloc[-1]["context_hour_sin"] <= 1.0
    assert -1.0 <= context.iloc[-1]["context_hour_cos"] <= 1.0


def test_tactical_context_enrichment_preserves_feature_time_order() -> None:
    index = pd.date_range("2026-01-01", periods=180, freq="h")
    bars = _bars(index)
    features = build_features(bars, horizon=3)
    enriched = enrich_with_tactical_context(features, bars, _bars(index, drift=0.05))
    assert set(TACTICAL_CONTEXT_COLUMNS).issubset(enriched.columns)
    assert enriched.index.is_monotonic_increasing
    assert enriched.index.max() <= features.index.max()
