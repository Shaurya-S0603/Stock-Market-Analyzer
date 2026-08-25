from __future__ import annotations

from dataclasses import dataclass


class TradingError(ValueError):
    pass


@dataclass
class Position:
    quantity: int = 0
    average_cost: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class Fill:
    side: str
    quantity: int
    price: float
    fee: float
    timestamp: object
    realized_pnl: float = 0.0
    reason: str = "manual"


class PaperPortfolio:
    def __init__(self, starting_cash: float = 100_000.0, commission_rate: float = 0.001, slippage_rate: float = 0.0005):
        if starting_cash <= 0 or commission_rate < 0 or slippage_rate < 0:
            raise ValueError("Portfolio settings must be non-negative and cash must be positive")
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.positions: dict[str, Position] = {}
        self.fills: list[Fill] = []

    def execute(self, symbol: str, side: str, quantity: int, price: float, timestamp=None, reason: str = "manual") -> Fill:
        side = side.lower()
        if side not in {"buy", "sell"} or quantity <= 0 or price <= 0:
            raise TradingError("side, quantity, and price are invalid")
        position = self.positions.setdefault(symbol.upper(), Position())
        execution_price = price * (1 + self.slippage_rate if side == "buy" else 1 - self.slippage_rate)
        gross = execution_price * quantity
        fee = gross * self.commission_rate
        if side == "buy":
            if self.cash < gross + fee:
                raise TradingError("insufficient cash")
            total_cost = position.average_cost * position.quantity + gross + fee
            position.quantity += quantity
            position.average_cost = total_cost / position.quantity
            self.cash -= gross + fee
            realized_pnl = 0.0
        else:
            if position.quantity < quantity:
                raise TradingError("insufficient shares")
            realized_pnl = (execution_price - position.average_cost) * quantity - fee
            position.realized_pnl += realized_pnl
            position.quantity -= quantity
            self.cash += gross - fee
            if position.quantity == 0:
                position.average_cost = 0.0
        fill = Fill(side, quantity, execution_price, fee, timestamp, realized_pnl=realized_pnl, reason=reason)
        self.fills.append(fill)
        return fill

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + sum(position.quantity * prices.get(symbol, position.average_cost) for symbol, position in self.positions.items())

    def summary(self, prices: dict[str, float]) -> dict[str, float]:
        equity = self.equity(prices)
        return {"cash": self.cash, "equity": equity, "pnl": equity - self.starting_cash, "return_pct": (equity / self.starting_cash - 1) * 100}

    def positions_snapshot(self, prices: dict[str, float]) -> list[dict[str, float | int | str]]:
        snapshot = []
        for symbol, position in self.positions.items():
            if position.quantity <= 0:
                continue
            market_price = float(prices.get(symbol, position.average_cost))
            market_value = market_price * position.quantity
            cost_basis = position.average_cost * position.quantity
            unrealized_pnl = market_value - cost_basis
            unrealized_pct = (market_price / position.average_cost - 1) * 100 if position.average_cost > 0 else 0.0
            snapshot.append(
                {
                    "symbol": symbol,
                    "quantity": position.quantity,
                    "avg_cost": position.average_cost,
                    "market_price": market_price,
                    "market_value": market_value,
                    "cost_basis": cost_basis,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pct": unrealized_pct,
                    "realized_pnl": position.realized_pnl,
                }
            )
        return snapshot
