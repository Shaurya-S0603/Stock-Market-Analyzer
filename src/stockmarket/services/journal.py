from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from ..storage import Store
from ..trading import PaperPortfolio
from .ai_trader import TradeDecision, TraderMode


@dataclass(frozen=True)
class TraderCycleSummary:
    cycle_id: str
    decisions: int
    executed: int
    rejected: int
    holds: int


class JournalService:
    """Persists AI-trader decisions and paper-account snapshots for audit and analysis."""

    def __init__(self, store: Store):
        self.store = store

    def record_cycle(self, decisions: list[TradeDecision], mode: TraderMode, portfolio: PaperPortfolio, prices: dict[str, float]) -> TraderCycleSummary:
        cycle_id = uuid4().hex[:12]
        executed = sum(1 for decision in decisions if decision.executed)
        rejected = sum(1 for decision in decisions if decision.decision == "REJECT")
        holds = sum(1 for decision in decisions if decision.decision in {"HOLD", "OFF"})
        self.store.add_trader_run(cycle_id, mode.value, len(decisions), executed)
        for decision in decisions:
            self.store.add_ai_decision(cycle_id, mode.value, decision)
        summary = portfolio.summary(prices)
        invested = max(summary["equity"] - summary["cash"], 0.0)
        exposure_pct = invested / summary["equity"] * 100.0 if summary["equity"] else 0.0
        self.store.add_portfolio_snapshot(summary["cash"], summary["equity"], summary["pnl"], exposure_pct)
        return TraderCycleSummary(cycle_id, len(decisions), executed, rejected, holds)
