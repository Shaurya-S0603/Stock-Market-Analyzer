from __future__ import annotations

from dataclasses import dataclass

from ..storage import Store


@dataclass(frozen=True)
class TraderAnalytics:
    cycles: int
    decisions: int
    executed_decisions: int
    rejected_decisions: int
    model_gate_pass_rate: float
    execution_rate: float
    closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    realized_pnl: float
    average_win: float
    average_loss: float
    profit_factor: float
    expectancy: float
    max_snapshot_drawdown_pct: float


def build_trader_analytics(store: Store) -> TraderAnalytics:
    decisions = store.ai_decisions(limit=10_000)
    runs = store.trader_runs(limit=10_000)
    orders = store.orders()
    snapshots = list(reversed(store.portfolio_snapshots(limit=10_000)))

    executed = [row for row in decisions if bool(row.get("executed"))]
    rejected = [row for row in decisions if row.get("decision") == "REJECT"]
    gated = [row for row in decisions if bool(row.get("model_gate_passed"))]
    ai_sells = [row for row in orders if row.get("side") == "sell" and str(row.get("reason", "")).startswith("ai_")]
    wins = [float(row.get("realized_pnl", 0.0) or 0.0) for row in ai_sells if float(row.get("realized_pnl", 0.0) or 0.0) > 0]
    losses = [float(row.get("realized_pnl", 0.0) or 0.0) for row in ai_sells if float(row.get("realized_pnl", 0.0) or 0.0) < 0]
    realized = sum(float(row.get("realized_pnl", 0.0) or 0.0) for row in ai_sells)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
    average_win = gross_profit / len(wins) if wins else 0.0
    average_loss = sum(losses) / len(losses) if losses else 0.0
    expectancy = realized / len(ai_sells) if ai_sells else 0.0

    max_drawdown = 0.0
    peak = None
    for snapshot in snapshots:
        equity = float(snapshot.get("equity", 0.0) or 0.0)
        peak = equity if peak is None else max(peak, equity)
        if peak and peak > 0:
            max_drawdown = min(max_drawdown, (equity / peak - 1.0) * 100.0)

    count = len(decisions)
    return TraderAnalytics(
        cycles=len(runs),
        decisions=count,
        executed_decisions=len(executed),
        rejected_decisions=len(rejected),
        model_gate_pass_rate=len(gated) / count if count else 0.0,
        execution_rate=len(executed) / count if count else 0.0,
        closed_trades=len(ai_sells),
        winning_trades=len(wins),
        losing_trades=len(losses),
        win_rate=len(wins) / len(ai_sells) if ai_sells else 0.0,
        realized_pnl=realized,
        average_win=average_win,
        average_loss=average_loss,
        profit_factor=profit_factor,
        expectancy=expectancy,
        max_snapshot_drawdown_pct=max_drawdown,
    )
