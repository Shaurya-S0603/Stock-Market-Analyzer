from datetime import timezone
from types import SimpleNamespace

import pandas as pd

from stockmarket.services.adaptive_exits import evaluate_adaptive_exit
from stockmarket.services.portfolio import PortfolioService, RiskPolicy
from stockmarket.storage import Store
from stockmarket.trading import PaperPortfolio


def _analysis(
    price: float,
    signal: str = "Hold",
    probability: float = 0.7,
    atr: float = 1.0,
    *,
    bearish: bool = False,
):
    index = pd.date_range("2026-01-01", periods=80, freq="h")
    close = pd.Series([100 + i * 0.05 for i in range(len(index))], index=index)
    bars = pd.DataFrame(
        {"Open": close, "High": close + 1.0, "Low": close - 1.0, "Close": close, "Volume": 1_000_000},
        index=index,
    )
    bars.iloc[-1, bars.columns.get_loc("Close")] = price
    direction = -1.0 if bearish else 1.0
    net_edge = -0.02 if bearish else 0.01
    features = {
        "atr": atr,
        "context_volatility_20": 0.01,
        "context_return_6": direction * 0.025,
        "context_return_24": direction * 0.05,
        "context_volume_ratio_20": 1.8,
        "context_volume_shock_6_20": direction * 0.6,
        "context_price_volume_confirmation": direction * 0.8,
        "context_trend_persistence": direction * 0.9,
        "daily_return_20": direction * 0.08,
        "daily_return_60": direction * 0.12,
        "daily_trend_20": direction * 0.05,
        "daily_trend_50": direction * 0.06,
    }
    return SimpleNamespace(
        symbol="MSFT",
        price=price,
        bars=bars,
        live_features=pd.DataFrame([features]),
        signal=SimpleNamespace(action=signal, net_edge=net_edge, confidence=1.0 - probability if signal == "Sell" else probability),
        predicted_return=net_edge,
        probability_profitable=probability,
        adaptive_buy_threshold=0.003,
        adaptive_sell_threshold=-0.003,
    )


def _manual_order_at(timestamp) -> dict:
    if hasattr(timestamp, "to_pydatetime"):
        timestamp = timestamp.to_pydatetime()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return {
        "symbol": "MSFT",
        "side": "buy",
        "created_at": timestamp.isoformat(),
        "reason": "rebalance_manual",
    }


def test_fresh_manual_allocation_ignores_immediate_sell_label() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("MSFT", "buy", 10, 100)
    analysis = _analysis(101, signal="Sell", probability=0.20, bearish=True)
    order = _manual_order_at(analysis.bars.index[-1])
    decision = evaluate_adaptive_exit(
        analysis,
        portfolio.positions["MSFT"],
        [order],
        RiskPolicy(True, 2, 4),
    )
    assert not decision.should_exit
    assert decision.reason == "acquisition_grace"
    assert decision.protected
    assert decision.holding_bars is not None and decision.holding_bars < 12


def test_hard_stop_can_exit_during_manual_acquisition_grace() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("MSFT", "buy", 10, 100)
    analysis = _analysis(95, signal="Sell", probability=0.20, bearish=True)
    order = _manual_order_at(analysis.bars.index[-1])
    decision = evaluate_adaptive_exit(
        analysis,
        portfolio.positions["MSFT"],
        [order],
        RiskPolicy(True, 2, 4),
    )
    assert decision.should_exit
    assert decision.reason == "adaptive_stop"


def test_confirmed_bearish_exit_allowed_after_holding_window() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("MSFT", "buy", 10, 100)
    analysis = _analysis(103, signal="Sell", probability=0.20, bearish=True)
    old_order = _manual_order_at(analysis.bars.index[0])
    decision = evaluate_adaptive_exit(
        analysis,
        portfolio.positions["MSFT"],
        [old_order],
        RiskPolicy(True, 2, 4),
    )
    assert decision.should_exit
    assert decision.reason == "research_bearish_reversal"
    assert decision.research_score < 0


def test_sell_label_without_bearish_factor_confirmation_holds_position() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("MSFT", "buy", 10, 100)
    analysis = _analysis(101, signal="Sell", probability=0.70, bearish=False)
    old_order = _manual_order_at(analysis.bars.index[0])
    decision = evaluate_adaptive_exit(
        analysis,
        portfolio.positions["MSFT"],
        [old_order],
        RiskPolicy(True, 2, 4),
    )
    assert not decision.should_exit
    assert decision.reason == "sell_not_confirmed"


def test_adaptive_exit_can_trigger_confirmed_confidence_decay() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("MSFT", "buy", 10, 100)
    policy = RiskPolicy(True, 2, 4, min_hold_probability=0.40)
    analysis = _analysis(101, probability=0.25, bearish=True)
    old_order = _manual_order_at(analysis.bars.index[0])
    decision = evaluate_adaptive_exit(analysis, portfolio.positions["MSFT"], [old_order], policy)
    assert decision.should_exit
    assert decision.reason == "confidence_decay_confirmed"


def test_portfolio_service_executes_hard_adaptive_exit_as_paper_order(tmp_path) -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("MSFT", "buy", 10, 100)
    store = Store(str(tmp_path / "paper.db"))
    service = PortfolioService(portfolio, store)
    events = service.apply_adaptive_exit_policy({"MSFT": _analysis(95, atr=1.2)}, RiskPolicy(True, 2, 4))
    assert events
    assert portfolio.positions["MSFT"].quantity == 0
    assert store.risk_events()[0]["event_type"] == "adaptive_stop"
