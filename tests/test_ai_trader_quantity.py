from types import SimpleNamespace

import pandas as pd

from stockmarket.services.ai_trader import AITraderConfig, AITraderService, TraderMode
from stockmarket.services.portfolio import PortfolioService
from stockmarket.services.risk import RiskLimits
from stockmarket.storage import Store
from stockmarket.trading import PaperPortfolio


def _analysis(
    symbol: str,
    action: str,
    confidence: float,
    price: float = 100.0,
    volatility: float = 0.10,
    *,
    bearish: bool | None = None,
):
    if bearish is None:
        bearish = action == "Sell"
    predicted = -0.02 if bearish else 0.02
    direction = -1.0 if bearish else 1.0
    probability = max(0.0, min(1.0, 1.0 - confidence if bearish else confidence))
    index = pd.date_range("2026-01-01", periods=80, freq="h")
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
    features = {
        "volatility_10": volatility,
        "context_volatility_20": max(volatility / 10.0, 0.005),
        "context_return_6": direction * 0.02,
        "context_return_24": direction * 0.04,
        "context_volume_ratio_20": 1.6,
        "context_volume_shock_6_20": direction * 0.5,
        "context_price_volume_confirmation": direction * 0.7,
        "context_trend_persistence": direction * 0.8,
        "daily_return_20": direction * 0.07,
        "daily_return_60": direction * 0.10,
        "daily_trend_20": direction * 0.04,
        "daily_trend_50": direction * 0.05,
    }
    return SimpleNamespace(
        symbol=symbol,
        price=price,
        predicted_return=predicted,
        signal=SimpleNamespace(
            action=action,
            confidence=confidence,
            net_edge=predicted,
        ),
        live_features=pd.DataFrame([features]),
        bars=bars,
        probability_profitable=probability,
        adaptive_buy_threshold=0.003,
        adaptive_sell_threshold=-0.003,
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


def test_sell_uses_full_open_quantity_after_bearish_research_confirmation(tmp_path) -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("TEST", "buy", 3, 100.0)
    store = Store(str(tmp_path / "paper.db"))
    service = PortfolioService(portfolio, store)
    config = AITraderConfig(
        mode=TraderMode.PAPER_AUTO,
        min_confidence=0.95,
        allocation_pct=10.0,
    )
    analysis = _analysis("TEST", "Sell", confidence=0.90, price=95.0, bearish=True)

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
    assert "Multi-factor bearish exit confirmed" in decisions[0].reason
    assert portfolio.positions["TEST"].quantity == 0


def test_fresh_manual_position_is_not_sold_from_one_model_label() -> None:
    portfolio = PaperPortfolio(10_000, commission_rate=0, slippage_rate=0)
    portfolio.execute("TEST", "buy", 3, 100.0)
    analysis = _analysis("TEST", "Sell", confidence=0.95, price=99.0, bearish=True)
    recent_buy = {
        "symbol": "TEST",
        "side": "buy",
        "created_at": analysis.bars.index[-1].isoformat(),
        "reason": "rebalance_manual",
    }
    decision = AITraderService().evaluate_symbol(
        analysis,
        model_gate_passed=False,
        portfolio=portfolio,
        config=AITraderConfig(mode=TraderMode.OBSERVE),
        prices={"TEST": 99.0},
        orders=[recent_buy],
    )
    assert decision.decision == "HOLD"
    assert decision.quantity == 0
    assert "position retained" in decision.reason
