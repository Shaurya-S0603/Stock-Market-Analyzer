import pandas as pd

from stockmarket.services.adaptive_exits import evaluate_adaptive_exit
from stockmarket.services.portfolio import PortfolioService, RiskPolicy
from stockmarket.storage import Store
from stockmarket.trading import PaperPortfolio


def _analysis(price: float, signal: str = "Hold", probability: float = 0.7, atr: float = 1.0):
    from types import SimpleNamespace

    index = pd.date_range("2026-01-01", periods=80, freq="h")
    close = pd.Series([100 + i * 0.05 for i in range(len(index))], index=index)
    bars = pd.DataFrame(
        {"Open": close, "High": close + 1.0, "Low": close - 1.0, "Close": close, "Volume": 1_000_000},
        index=index,
    )
    bars.iloc[-1, bars.columns.get_loc("Close")] = price
    return SimpleNamespace(
        symbol="MSFT",
        price=price,
        bars=bars,
        live_features=pd.DataFrame([{"atr": atr}]),
        signal=SimpleNamespace(action=signal),
        probability_profitable=probability,
    )


def test_adaptive_exit_uses_signal_reversal_before_static_thresholds() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("MSFT", "buy", 10, 100)
    decision = evaluate_adaptive_exit(_analysis(101, signal="Sell"), portfolio.positions["MSFT"], [], RiskPolicy(True, 2, 4))
    assert decision.should_exit
    assert decision.reason == "signal_reversal"


def test_adaptive_exit_can_trigger_confidence_decay() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("MSFT", "buy", 10, 100)
    policy = RiskPolicy(True, 2, 4, min_hold_probability=0.40)
    decision = evaluate_adaptive_exit(_analysis(100.5, probability=0.25), portfolio.positions["MSFT"], [], policy)
    assert decision.should_exit
    assert decision.reason == "confidence_decay"


def test_portfolio_service_executes_adaptive_exit_as_paper_order(tmp_path) -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("MSFT", "buy", 10, 100)
    store = Store(str(tmp_path / "paper.db"))
    service = PortfolioService(portfolio, store)
    events = service.apply_adaptive_exit_policy({"MSFT": _analysis(96, atr=1.2)}, RiskPolicy(True, 2, 4))
    assert events
    assert portfolio.positions["MSFT"].quantity == 0
    assert store.risk_events()[0]["event_type"] in {"adaptive_stop", "confidence_decay", "signal_reversal", "adaptive_take_profit", "time_stop"}
