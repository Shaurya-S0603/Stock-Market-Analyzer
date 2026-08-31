from __future__ import annotations

from dataclasses import dataclass

from ..trading import PaperPortfolio


@dataclass(frozen=True)
class AllocationSnapshotRow:
    symbol: str
    target_pct: float
    actual_pct: float
    drift_pct: float
    market_value: float
    remaining_capacity: float
    is_cash: bool = False


def build_allocation_snapshot(
    portfolio: PaperPortfolio,
    prices: dict[str, float],
    target_allocations: dict[str, float],
    cash_target_pct: float,
) -> list[AllocationSnapshotRow]:
    equity = float(portfolio.equity(prices))
    targets = {symbol.upper(): float(weight) for symbol, weight in target_allocations.items()}
    rows: list[AllocationSnapshotRow] = []

    for symbol, target_pct in targets.items():
        position = portfolio.positions.get(symbol)
        quantity = position.quantity if position and position.quantity > 0 else 0
        mark = prices.get(symbol, position.average_cost if position else 0.0)
        market_value = float(quantity * mark)
        actual_pct = market_value / equity * 100.0 if equity > 0 else 0.0
        target_value = equity * target_pct / 100.0 if equity > 0 else 0.0
        rows.append(
            AllocationSnapshotRow(
                symbol=symbol,
                target_pct=target_pct,
                actual_pct=actual_pct,
                drift_pct=actual_pct - target_pct,
                market_value=market_value,
                remaining_capacity=max(target_value - market_value, 0.0),
            )
        )

    for symbol, position in portfolio.positions.items():
        if symbol in targets or position.quantity <= 0:
            continue
        mark = prices.get(symbol, position.average_cost)
        market_value = float(position.quantity * mark)
        actual_pct = market_value / equity * 100.0 if equity > 0 else 0.0
        rows.append(
            AllocationSnapshotRow(
                symbol=symbol,
                target_pct=0.0,
                actual_pct=actual_pct,
                drift_pct=actual_pct,
                market_value=market_value,
                remaining_capacity=0.0,
            )
        )

    cash_value = float(portfolio.cash)
    cash_actual_pct = cash_value / equity * 100.0 if equity > 0 else 0.0
    rows.append(
        AllocationSnapshotRow(
            symbol="Cash",
            target_pct=float(cash_target_pct),
            actual_pct=cash_actual_pct,
            drift_pct=cash_actual_pct - float(cash_target_pct),
            market_value=cash_value,
            remaining_capacity=max(equity * float(cash_target_pct) / 100.0 - cash_value, 0.0) if equity > 0 else 0.0,
            is_cash=True,
        )
    )
    return rows
