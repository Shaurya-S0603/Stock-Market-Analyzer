from __future__ import annotations

from dataclasses import dataclass

from ..storage import Store
from ..trading import Fill, PaperPortfolio


@dataclass(frozen=True)
class RiskPolicy:
    enabled: bool = False
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 4.0

    def validate(self) -> None:
        if self.stop_loss_pct <= 0 or self.take_profit_pct <= 0:
            raise ValueError("Risk thresholds must be positive")


class PortfolioService:
    """Coordinates paper execution, persistence, and risk automation."""

    def __init__(self, portfolio: PaperPortfolio, store: Store):
        self.portfolio = portfolio
        self.store = store

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
        return fill

    def apply_risk_policy(self, latest_prices: dict[str, float], policy: RiskPolicy) -> list[str]:
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
                events.append(
                    f"Auto-exit {symbol}: {reason.replace('_', ' ')} at ${fill.price:,.2f} for {fill.quantity} shares."
                )
        return events
