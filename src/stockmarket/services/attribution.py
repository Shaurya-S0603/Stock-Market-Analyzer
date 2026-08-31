from __future__ import annotations

from dataclasses import dataclass

from ..storage import Store
from ..trading import PaperPortfolio


@dataclass(frozen=True)
class SymbolAttribution:
    symbol: str
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    fees: float
    orders: int
    gross_contribution_pct: float


@dataclass(frozen=True)
class PortfolioAttribution:
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    fees: float
    orders: int
    symbols: tuple[SymbolAttribution, ...]


def build_portfolio_attribution(
    store: Store,
    portfolio: PaperPortfolio,
    prices: dict[str, float],
) -> PortfolioAttribution:
    orders = store.orders()
    realized_by_symbol: dict[str, float] = {}
    fees_by_symbol: dict[str, float] = {}
    count_by_symbol: dict[str, int] = {}
    for order in orders:
        symbol = str(order.get("symbol", "")).upper()
        if not symbol:
            continue
        realized_by_symbol[symbol] = realized_by_symbol.get(symbol, 0.0) + float(order.get("realized_pnl", 0.0) or 0.0)
        fees_by_symbol[symbol] = fees_by_symbol.get(symbol, 0.0) + float(order.get("fee", 0.0) or 0.0)
        count_by_symbol[symbol] = count_by_symbol.get(symbol, 0) + 1

    unrealized_by_symbol = {
        str(row["symbol"]): float(row["unrealized_pnl"])
        for row in portfolio.positions_snapshot(prices)
    }
    symbols = sorted(set(realized_by_symbol) | set(unrealized_by_symbol) | set(count_by_symbol))
    totals = {
        symbol: realized_by_symbol.get(symbol, 0.0) + unrealized_by_symbol.get(symbol, 0.0)
        for symbol in symbols
    }
    gross_absolute = sum(abs(value) for value in totals.values())
    rows = tuple(
        SymbolAttribution(
            symbol=symbol,
            realized_pnl=realized_by_symbol.get(symbol, 0.0),
            unrealized_pnl=unrealized_by_symbol.get(symbol, 0.0),
            total_pnl=totals[symbol],
            fees=fees_by_symbol.get(symbol, 0.0),
            orders=count_by_symbol.get(symbol, 0),
            gross_contribution_pct=(abs(totals[symbol]) / gross_absolute * 100.0) if gross_absolute > 0 else 0.0,
        )
        for symbol in sorted(symbols, key=lambda item: abs(totals[item]), reverse=True)
    )
    return PortfolioAttribution(
        realized_pnl=sum(realized_by_symbol.values()),
        unrealized_pnl=sum(unrealized_by_symbol.values()),
        total_pnl=sum(totals.values()),
        fees=sum(fees_by_symbol.values()),
        orders=sum(count_by_symbol.values()),
        symbols=rows,
    )
