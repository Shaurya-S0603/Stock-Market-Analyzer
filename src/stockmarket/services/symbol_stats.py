from __future__ import annotations

from dataclasses import dataclass

from ..storage import Store


@dataclass(frozen=True)
class SymbolStrategyStats:
    symbol: str
    decisions: int
    executed_decisions: int
    rejected_decisions: int
    model_gate_pass_rate: float
    average_confidence: float
    average_net_edge: float
    closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    realized_pnl: float
    expectancy: float


def build_symbol_strategy_stats(store: Store) -> list[SymbolStrategyStats]:
    decisions = store.ai_decisions(limit=50_000)
    orders = store.orders()
    symbols = sorted(
        {str(row.get("symbol", "")).upper() for row in decisions + orders if str(row.get("symbol", "")).strip()}
    )
    stats: list[SymbolStrategyStats] = []

    for symbol in symbols:
        symbol_decisions = [row for row in decisions if str(row.get("symbol", "")).upper() == symbol]
        executed = [row for row in symbol_decisions if bool(row.get("executed"))]
        rejected = [row for row in symbol_decisions if str(row.get("decision", "")) == "REJECT"]
        gated = [row for row in symbol_decisions if bool(row.get("model_gate_passed"))]
        automated_sells = [
            row
            for row in orders
            if str(row.get("symbol", "")).upper() == symbol
            and str(row.get("side", "")).lower() == "sell"
            and str(row.get("reason", "manual")) != "manual"
        ]
        pnl_values = [float(row.get("realized_pnl", 0.0) or 0.0) for row in automated_sells]
        wins = [value for value in pnl_values if value > 0]
        losses = [value for value in pnl_values if value < 0]
        realized = sum(pnl_values)
        decision_count = len(symbol_decisions)
        closed = len(automated_sells)
        stats.append(
            SymbolStrategyStats(
                symbol=symbol,
                decisions=decision_count,
                executed_decisions=len(executed),
                rejected_decisions=len(rejected),
                model_gate_pass_rate=len(gated) / decision_count if decision_count else 0.0,
                average_confidence=(sum(float(row.get("confidence", 0.0) or 0.0) for row in symbol_decisions) / decision_count) if decision_count else 0.0,
                average_net_edge=(sum(float(row.get("net_edge", 0.0) or 0.0) for row in symbol_decisions) / decision_count) if decision_count else 0.0,
                closed_trades=closed,
                winning_trades=len(wins),
                losing_trades=len(losses),
                win_rate=len(wins) / closed if closed else 0.0,
                realized_pnl=realized,
                expectancy=realized / closed if closed else 0.0,
            )
        )

    return sorted(stats, key=lambda row: (abs(row.realized_pnl), row.decisions, row.symbol), reverse=True)
