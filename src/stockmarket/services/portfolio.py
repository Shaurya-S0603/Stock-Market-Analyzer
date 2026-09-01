from __future__ import annotations

from dataclasses import dataclass

from ..storage import Store
from ..trading import Fill, PaperPortfolio
from .adaptive_exits import evaluate_adaptive_exit
from .persistent_state import PersistentPaperState


@dataclass(frozen=True)
class RiskPolicy:
    enabled: bool = False
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 4.0
    adaptive: bool = True
    atr_stop_multiple: float = 2.0
    reward_to_risk: float = 1.75
    trailing_lookback_bars: int = 30
    min_hold_probability: float = 0.38
    max_holding_bars: int = 60

    def validate(self) -> None:
        if self.stop_loss_pct <= 0 or self.take_profit_pct <= 0:
            raise ValueError("Risk thresholds must be positive")
        if self.atr_stop_multiple <= 0 or self.reward_to_risk <= 0:
            raise ValueError("Adaptive exit multipliers must be positive")
        if self.trailing_lookback_bars < 2 or self.max_holding_bars < 1:
            raise ValueError("Adaptive exit lookback and holding limits must be positive")
        if not 0.0 <= self.min_hold_probability <= 1.0:
            raise ValueError("min_hold_probability must be between 0 and 1")


class PortfolioService:
    """Coordinates paper execution, order persistence, and account-state recovery."""

    def __init__(self, portfolio: PaperPortfolio, store: Store, paper_state: PersistentPaperState | None = None):
        self.portfolio = portfolio
        self.store = store
        self.paper_state = paper_state

    def persist_state(self) -> None:
        if self.paper_state is not None:
            self.paper_state.save(self.portfolio)

    def execute(self, symbol: str, side: str, quantity: int, price: float, reason: str = "manual") -> Fill:
        fill = self.portfolio.execute(symbol, side, quantity, price, reason=reason)
        self.store.add_order(
            symbol,
            fill.side,
            fill.quantity,
            fill.price,
            fill.fee,
            fill.realized_pnl,
            fill.reason,
        )
        self.persist_state()
        return fill

    def apply_risk_policy(self, latest_prices: dict[str, float], policy: RiskPolicy) -> list[str]:
        """Backward-compatible static stop/target path."""
        policy.validate()
        if not policy.enabled:
            return []
        events: list[str] = []
        for symbol, position in list(self.portfolio.positions.items()):
            if position.quantity <= 0 or position.average_cost <= 0:
                continue
            mark = latest_prices.get(symbol)
            if mark is None:
                continue
            stop_trigger = position.average_cost * (1.0 - policy.stop_loss_pct / 100.0)
            take_trigger = position.average_cost * (1.0 + policy.take_profit_pct / 100.0)
            reason = None
            if mark <= stop_trigger:
                reason = "stop_loss"
            elif mark >= take_trigger:
                reason = "take_profit"
            if reason:
                fill = self.execute(symbol, "sell", position.quantity, mark, reason=reason)
                detail = f"Auto-exit {symbol}: {reason.replace('_', ' ')} at ${fill.price:,.2f} for {fill.quantity} shares."
                self.store.add_risk_event(reason, detail, symbol)
                events.append(detail)
        return events

    def apply_adaptive_exit_policy(self, analyses: dict, policy: RiskPolicy) -> list[str]:
        policy.validate()
        if not policy.enabled:
            return []
        if not policy.adaptive:
            return self.apply_risk_policy({symbol: float(analysis.price) for symbol, analysis in analyses.items()}, policy)

        orders = self.store.orders()
        events: list[str] = []
        for symbol, position in list(self.portfolio.positions.items()):
            if position.quantity <= 0 or symbol not in analyses:
                continue
            analysis = analyses[symbol]
            decision = evaluate_adaptive_exit(analysis, position, orders, policy)
            if not decision.should_exit:
                continue
            fill = self.execute(symbol, "sell", position.quantity, float(analysis.price), reason=decision.reason)
            detail = (
                f"Adaptive paper exit {symbol}: {decision.reason.replace('_', ' ')} at ${fill.price:,.2f}; "
                f"stop ${decision.stop_price:,.2f}, target ${decision.target_price:,.2f}, "
                f"profitable probability {decision.probability_profitable:.0%}."
            )
            self.store.add_risk_event(decision.reason, detail, symbol)
            events.append(detail)
        return events
