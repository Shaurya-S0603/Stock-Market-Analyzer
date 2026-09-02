from __future__ import annotations

from dataclasses import dataclass

from ..benchmarks import assess_trading_evidence
from .analysis import AnalysisRequest, AnalysisService, SymbolAnalysis, WatchlistAnalysis


@dataclass(frozen=True)
class PortfolioSignalState:
    symbol: str
    analysis: SymbolAnalysis
    model_gate_passed: bool
    model_gate_reason: str
    target_weight: float
    evidence_tier: str = "strong"
    evidence_multiplier: float = 1.0


@dataclass
class PortfolioResearchCycle:
    states: dict[str, PortfolioSignalState]
    unavailable: dict[str, str]

    @property
    def symbols_evaluated(self) -> int:
        return len(self.states)

    @property
    def model_gates(self) -> dict[str, bool]:
        return {symbol: state.model_gate_passed for symbol, state in self.states.items()}

    @property
    def analyses(self) -> dict[str, SymbolAnalysis]:
        return {symbol: state.analysis for symbol, state in self.states.items()}


class PortfolioCycleService:
    """Runs one research cycle across the configured portfolio universe before any simulated execution."""

    def __init__(self, analysis_service: AnalysisService):
        self.analysis_service = analysis_service

    def run(
        self,
        symbols: list[str],
        request: AnalysisRequest,
        allocations: dict[str, float] | None = None,
        watchlist: WatchlistAnalysis | None = None,
    ) -> PortfolioResearchCycle:
        allocation_map = {symbol.upper(): float(weight) for symbol, weight in (allocations or {}).items()}
        watchlist = watchlist or self.analysis_service.analyze_watchlist(symbols, request)
        states: dict[str, PortfolioSignalState] = {}
        for symbol in symbols:
            analysis = watchlist.available.get(symbol)
            if analysis is None:
                continue
            try:
                rows, strict_gate = self.analysis_service.benchmark_report(analysis)
                trading_gate = assess_trading_evidence(rows)
                passed = bool(trading_gate.approved)
                reason = (
                    f"Trading evidence {trading_gate.tier}: {trading_gate.reason} "
                    f"Strict research gate: {'PASS' if strict_gate.approved else 'HOLD'}."
                )
                evidence_tier = trading_gate.tier
                evidence_multiplier = float(trading_gate.size_multiplier)
            except ValueError as exc:
                passed = False
                reason = f"Benchmark gate unavailable: {exc}"
                evidence_tier = "unavailable"
                evidence_multiplier = 0.0
            states[symbol] = PortfolioSignalState(
                symbol=symbol,
                analysis=analysis,
                model_gate_passed=passed,
                model_gate_reason=reason,
                target_weight=float(allocation_map.get(symbol.upper(), 0.0)),
                evidence_tier=evidence_tier,
                evidence_multiplier=evidence_multiplier,
            )
        return PortfolioResearchCycle(states=states, unavailable=dict(watchlist.unavailable))
