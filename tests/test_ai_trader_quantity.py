from types import SimpleNamespace

import pandas as pd

from stockmarket.services.ai_trader import AITraderConfig, AITraderService, TraderMode
from stockmarket.services.portfolio import PortfolioService
from stockmarket.services.risk import RiskLimits
from stockmarket.storage import Store
from stockmarket.trading import PaperPortfolio


def _analysis(symbol: str, action: str, confidence: float, price: float = 100.0, volatility: float = 0.10):
    predicted = 0.02 if action == "Buy" else -0.02
    return SimpleNamespace(
        symbol=symbol,
        price=price,
        predicted_return=predicted,
        signal=SimpleNamespace(
            action=action,
            confidence=confidence,
            net_edge=abs(predicted),
        ),
        live_features=pd.DataFrame([{"volatility_10": volatility}]),
    )


def test_buy_does_not_round_valid_whole_share_budget_to_zero() -> None:
    portfolio = PaperPortfolio(1_000, commission_rate=0, slippage_rate=0)
    config = AITraderConfig(
        mode=TraderMode.OBSERVE,
        min_confidence=0.60,
        allocation_pct=10.0,
        risk_limits=RiskLimits(
            max_position_pct=10.0,
            max_portfolio_exposure_pct=60.0,
            max_open_positions=6,
            max_daily_trades=12,
            max_daily_loss_pct=3.0,
            volatility_target_pct=1.5,
        ),
    )

    decision = AITraderService().evaluate_symbol(
        _analysis("TEST", "Buy", confidence=0.65, price=100.0, volatility=0.10),
        model_gate_passed=True,
        portfolio=portfolio,
        config=config,
        prices={"TEST": 100.0},
        orders=[],
    )

    assert decision.decision == "BUY"
    assert decision.quantity == 1
    assert "Whole-share sizing floor applied" in decision.reason


def test_sell_uses_full_open_quantity_even_when_entry_gates_fail(tmp_path) -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("TEST", "buy", 3, 100.0)
    store = Store(str(tmp_path / "paper.db"))
    service = PortfolioService(portfolio, store)
    config = AITraderConfig(
        mode=TraderMode.PAPER_AUTO,
        min_confidence=0.95,
        allocation_pct=10.0,
    )
    analysis = _analysis("TEST", "Sell", confidence=0.10, price=95.0)

    decisions = AITraderService().run_cycle(
        analyses={"TEST": analysis},
        model_gates={"TEST": False},
        portfolio=portfolio,
        portfolio_service=service,
        config=config,
    )

    assert decisions[0].decision == "SELL"
    assert decisions[0].quantity == 3
    assert decisions[0].executed
    assert portfolio.positions["TEST"].quantity == 0
