from __future__ import annotations

from dataclasses import dataclass

from ..trading import PaperPortfolio


@dataclass(frozen=True)
class RebalanceInstruction:
    symbol: str
    side: str
    quantity: int
    price: float
    estimated_value: float
    current_pct: float
    target_pct: float
    reason: str


@dataclass(frozen=True)
class PaperRebalancePlan:
    tolerance_pct: float
    instructions: tuple[RebalanceInstruction, ...]
    estimated_cash_after: float
    target_cash_value: float


def build_rebalance_plan(
    portfolio: PaperPortfolio,
    prices: dict[str, float],
    target_allocations: dict[str, float],
    cash_target_pct: float,
    tolerance_pct: float = 2.0,
) -> PaperRebalancePlan:
    if tolerance_pct < 0:
        raise ValueError("tolerance_pct must be non-negative")
    targets = {symbol.upper(): float(weight) for symbol, weight in target_allocations.items()}
    if abs(sum(targets.values()) + float(cash_target_pct) - 100.0) > 0.05:
        raise ValueError("Target allocations plus cash target must total 100%")

    equity = float(portfolio.equity(prices))
    if equity <= 0:
        return PaperRebalancePlan(float(tolerance_pct), tuple(), float(portfolio.cash), 0.0)

    current_values: dict[str, float] = {}
    for symbol, position in portfolio.positions.items():
        if position.quantity <= 0:
            continue
        mark = float(prices.get(symbol, position.average_cost))
        current_values[symbol] = float(position.quantity * mark)

    sells: list[RebalanceInstruction] = []
    buy_candidates: list[tuple[float, str, float, float, float]] = []
    all_symbols = sorted(set(targets) | set(current_values))
    for symbol in all_symbols:
        target_pct = float(targets.get(symbol, 0.0))
        current_value = float(current_values.get(symbol, 0.0))
        current_pct = current_value / equity * 100.0
        drift = current_pct - target_pct
        mark = float(prices.get(symbol, portfolio.positions.get(symbol).average_cost if portfolio.positions.get(symbol) else 0.0))
        if mark <= 0:
            continue
        if drift > tolerance_pct:
            excess_value = max(current_value - equity * target_pct / 100.0, 0.0)
            position = portfolio.positions.get(symbol)
            quantity = min(int(excess_value / mark), position.quantity if position else 0)
            if quantity > 0:
                sells.append(
                    RebalanceInstruction(
                        symbol=symbol,
                        side="sell",
                        quantity=quantity,
                        price=mark,
                        estimated_value=quantity * mark,
                        current_pct=current_pct,
                        target_pct=target_pct,
                        reason=f"Actual weight is {drift:.1f} percentage points above target.",
                    )
                )
        elif drift < -tolerance_pct and target_pct > 0:
            shortfall_value = max(equity * target_pct / 100.0 - current_value, 0.0)
            buy_candidates.append((abs(drift), symbol, mark, current_pct, shortfall_value))

    sells.sort(key=lambda item: (item.current_pct - item.target_pct, item.symbol), reverse=True)
    estimated_cash = float(portfolio.cash) + sum(item.estimated_value for item in sells)
    target_cash_value = equity * float(cash_target_pct) / 100.0
    spendable_cash = max(estimated_cash - target_cash_value, 0.0)

    buys: list[RebalanceInstruction] = []
    for _, symbol, mark, current_pct, shortfall_value in sorted(buy_candidates, reverse=True):
        target_pct = float(targets[symbol])
        budget = min(shortfall_value, spendable_cash)
        quantity = int(budget / mark)
        if quantity <= 0:
            continue
        estimated_value = quantity * mark
        buys.append(
            RebalanceInstruction(
                symbol=symbol,
                side="buy",
                quantity=quantity,
                price=mark,
                estimated_value=estimated_value,
                current_pct=current_pct,
                target_pct=target_pct,
                reason=f"Actual weight is {target_pct - current_pct:.1f} percentage points below target.",
            )
        )
        spendable_cash = max(spendable_cash - estimated_value, 0.0)

    instructions = tuple(sells + buys)
    estimated_cash_after = estimated_cash - sum(item.estimated_value for item in buys)
    return PaperRebalancePlan(float(tolerance_pct), instructions, estimated_cash_after, target_cash_value)
