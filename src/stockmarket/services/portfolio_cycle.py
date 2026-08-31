from __future__ import annotations

from dataclasses import dataclass

from .analysis import AnalysisRequest, AnalysisService, SymbolAnalysis


@dataclass(frozen=True)
class PortfolioSignalState:
    symbol: str
    analysis: SymbolAnalysis
    model_gate_passed: bool
    model_gate_reason: str
    target_weight: float


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
    ) -> PortfolioResearchCycle:
        allocation_map = {symbol.upper(): float(weight) for symbol, weight in (allocations or {}).items()}
        watchlist = self.analysis_service.analyze_watchlist(symbols, request)
        states: dict[str, PortfolioSignalState] = {}
        for symbol in symbols:
            analysis = watchlist.available.get(symbol)
            if analysis is None:
                continue
            try:
                _, gate = self.analysis_service.benchmark_report(analysis)
                passed = bool(gate.approved)
                reason = str(gate.reason)
            except ValueError as exc:
                passed = False
                reason = f"Benchmark gate unavailable: {exc}"
            states[symbol] = PortfolioSignalState(
                symbol=symbol,
                analysis=analysis,
                model_gate_passed=passed,
                model_gate_reason=reason,
                target_weight=float(allocation_map.get(symbol.upper(), 0.0)),
            )
        return PortfolioResearchCycle(states=states, unavailable=dict(watchlist.unavailable))
