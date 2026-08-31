from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..trading import PaperPortfolio


@dataclass(frozen=True)
class RiskLimits:
    max_position_pct: float = 10.0
    max_portfolio_exposure_pct: float = 60.0
    max_open_positions: int = 6
    max_daily_trades: int = 12
    max_daily_loss_pct: float = 3.0
    volatility_target_pct: float = 1.5

    def validate(self) -> None:
        if not 0.1 <= self.max_position_pct <= 100:
            raise ValueError("max_position_pct must be between 0.1 and 100")
        if not 0.1 <= self.max_portfolio_exposure_pct <= 100:
            raise ValueError("max_portfolio_exposure_pct must be between 0.1 and 100")
        if self.max_open_positions < 1 or self.max_daily_trades < 1:
            raise ValueError("position and trade limits must be positive")
        if not 0.1 <= self.max_daily_loss_pct <= 100:
            raise ValueError("max_daily_loss_pct must be between 0.1 and 100")
        if self.volatility_target_pct <= 0:
            raise ValueError("volatility_target_pct must be positive")


@dataclass(frozen=True)
class RiskAssessment:
    approved: bool
    quantity: int
    reason: str
    projected_exposure_pct: float
    allocation_value: float
    volatility_adjustment: float
    symbol_cap_pct: float = 0.0
    symbol_capacity_remaining: float = 0.0


def _today_order_stats(orders: list[dict]) -> tuple[int, float]:
    today = datetime.now(timezone.utc).date()
    count = 0
    realized = 0.0
    for order in orders:
        raw = str(order.get("created_at", ""))
        try:
            timestamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                timestamp = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        if timestamp.date() == today:
            count += 1
            realized += float(order.get("realized_pnl", 0.0) or 0.0)
    return count, realized


class RiskEngine:
    def assess_entry(
        self,
        symbol: str,
        price: float,
        confidence: float,
        recent_volatility: float,
        portfolio: PaperPortfolio,
        prices: dict[str, float],
        orders: list[dict],
        target_allocation_pct: float,
        limits: RiskLimits,
        symbol_allocation_pct: float | None = None,
    ) -> RiskAssessment:
        limits.validate()
        symbol = symbol.upper()
        equity = portfolio.equity(prices)
        open_positions = [position for position in portfolio.positions.values() if position.quantity > 0]
        daily_trades, daily_realized_pnl = _today_order_stats(orders)
        current_exposure_value = sum(
            position.quantity * prices.get(ticker, position.average_cost)
            for ticker, position in portfolio.positions.items()
            if position.quantity > 0
        )
        current_exposure_pct = current_exposure_value / equity * 100.0 if equity > 0 else 0.0
        configured_symbol_cap = limits.max_position_pct if symbol_allocation_pct is None else max(0.0, float(symbol_allocation_pct))
        effective_symbol_cap_pct = min(limits.max_position_pct, configured_symbol_cap)
        current_position = portfolio.positions.get(symbol)
        current_symbol_value = 0.0
        if current_position and current_position.quantity > 0:
            current_symbol_value = current_position.quantity * prices.get(symbol, current_position.average_cost)
        symbol_cap_value = equity * effective_symbol_cap_pct / 100.0 if equity > 0 else 0.0
        symbol_capacity = max(symbol_cap_value - current_symbol_value, 0.0)

        def reject(reason: str) -> RiskAssessment:
            return RiskAssessment(
                False,
                0,
                reason,
                current_exposure_pct,
                0.0,
                0.0,
                effective_symbol_cap_pct,
                symbol_capacity,
            )

        if symbol_allocation_pct is not None and configured_symbol_cap <= 0:
            return reject("Symbol has no enabled portfolio allocation.")
        if daily_trades >= limits.max_daily_trades:
            return reject("Daily paper-trade limit reached.")
        if daily_realized_pnl <= -(portfolio.starting_cash * limits.max_daily_loss_pct / 100.0):
            return reject("Daily realized-loss limit reached.")
        if len(open_positions) >= limits.max_open_positions:
            return reject("Maximum number of open paper positions reached.")
        if current_exposure_pct >= limits.max_portfolio_exposure_pct:
            return reject("Portfolio exposure cap reached.")
        if symbol_capacity <= 0:
            return reject("Symbol allocation ceiling reached.")

        volatility_pct = max(abs(float(recent_volatility)) * 100.0, 0.05)
        volatility_adjustment = min(1.0, max(0.25, limits.volatility_target_pct / volatility_pct))
        confidence_adjustment = min(1.0, max(0.25, float(confidence)))
        target_budget = portfolio.cash * (target_allocation_pct / 100.0) * confidence_adjustment * volatility_adjustment
        exposure_room = max(equity * limits.max_portfolio_exposure_pct / 100.0 - current_exposure_value, 0.0)
        allocation_value = min(target_budget, symbol_capacity, exposure_room, portfolio.cash)
        estimated_unit_cost = price * (1.0 + portfolio.slippage_rate) * (1.0 + portfolio.commission_rate)
        quantity = int(allocation_value / estimated_unit_cost) if estimated_unit_cost > 0 else 0
        if quantity < 1:
            return reject("Risk-adjusted allocation is too small for one paper share.")
        projected_value = current_exposure_value + quantity * price
        projected_exposure_pct = projected_value / equity * 100.0 if equity > 0 else 0.0
        remaining_after_order = max(symbol_capacity - quantity * price, 0.0)
        return RiskAssessment(
            True,
            quantity,
            "Portfolio and symbol-allocation risk checks passed.",
            projected_exposure_pct,
            quantity * price,
            volatility_adjustment,
            effective_symbol_cap_pct,
            remaining_after_order,
        )
