from types import SimpleNamespace

import pandas as pd

from stockmarket.services.research_intelligence import (
    compute_research_conviction,
    evaluate_research_exit,
    position_lifecycle,
    research_entry_adjustment,
)


def _analysis(direction: float = 1.0, probability: float = 0.75, signal: str = "Buy"):
    index = pd.date_range("2026-01-01", periods=100, freq="h")
    bars = pd.DataFrame(
        {
            "Open": 100.0,
            "High": 101.0,
            "Low": 99.0,
            "Close": 100.0,
            "Volume": 1_000_000,
        },
        index=index,
    )
    net_edge = direction * 0.012
    return SimpleNamespace(
        symbol="TEST",
        price=100.0,
        bars=bars,
        signal=SimpleNamespace(action=signal, net_edge=net_edge, confidence=probability if direction > 0 else 1.0 - probability),
        predicted_return=net_edge,
        probability_profitable=probability,
        adaptive_buy_threshold=0.003,
        adaptive_sell_threshold=-0.003,
        live_features=pd.DataFrame([
            {
                "context_volatility_20": 0.01,
                "context_return_6": direction * 0.025,
                "context_return_24": direction * 0.055,
                "context_volume_ratio_20": 1.7,
                "context_volume_shock_6_20": direction * 0.55,
                "context_price_volume_confirmation": direction * 0.75,
                "context_trend_persistence": direction * 0.85,
                "daily_return_20": direction * 0.08,
                "daily_return_60": direction * 0.14,
                "daily_trend_20": direction * 0.05,
                "daily_trend_50": direction * 0.06,
            }
        ]),
    )


def test_research_conviction_distinguishes_bullish_and_bearish_evidence() -> None:
    bullish = compute_research_conviction(_analysis(1.0, 0.80, "Buy"))
    bearish = compute_research_conviction(_analysis(-1.0, 0.20, "Sell"))
    assert bullish.score > 0.25
    assert bullish.positive_votes >= 3
    assert bearish.score < -0.25
    assert bearish.negative_votes >= 3


def test_strongly_contradictory_research_can_block_entry() -> None:
    analysis = _analysis(-1.0, 0.20, "Buy")
    adjustment, conviction = research_entry_adjustment(analysis)
    assert conviction.negative_votes >= 3
    assert adjustment == 0.0


def test_manual_rebalance_has_longer_acquisition_grace() -> None:
    analysis = _analysis(-1.0, 0.20, "Sell")
    order = {
        "symbol": "TEST",
        "side": "buy",
        "created_at": analysis.bars.index[-1].isoformat(),
        "reason": "rebalance_manual",
    }
    lifecycle = position_lifecycle(analysis, [order])
    assert lifecycle.minimum_hold_bars == 12
    assert lifecycle.protected
    assert lifecycle.bars_held == 1


def test_bearish_exit_requires_both_elapsed_hold_and_factor_confirmation() -> None:
    analysis = _analysis(-1.0, 0.20, "Sell")
    fresh = {
        "symbol": "TEST",
        "side": "buy",
        "created_at": analysis.bars.index[-1].isoformat(),
        "reason": "rebalance_manual",
    }
    old = {
        "symbol": "TEST",
        "side": "buy",
        "created_at": analysis.bars.index[0].isoformat(),
        "reason": "rebalance_manual",
    }
    assert not evaluate_research_exit(analysis, [fresh]).should_exit
    confirmed = evaluate_research_exit(analysis, [old])
    assert confirmed.should_exit
    assert confirmed.conviction.negative_votes >= 3
