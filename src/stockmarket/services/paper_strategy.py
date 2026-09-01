from __future__ import annotations

from dataclasses import dataclass, replace

from .ai_trader import AITraderConfig, AITraderService, TradeDecision, TraderMode
from .correlation import build_return_correlation_matrix, candidate_portfolio_correlation
from .opportunity import OpportunityRanker, RankedOpportunity
from .portfolio import PortfolioService
from .portfolio_cycle import PortfolioResearchCycle
from .portfolio_optimizer import OptimizedOpportunity, PortfolioOptimizer


@dataclass
class PaperStrategyCycleResult:
    decisions: list[TradeDecision]
    ranked_opportunities: list[RankedOpportunity]
    optimized_opportunities: list[OptimizedOpportunity]


class PaperOnlyPortfolioStrategy:
    """Coordinates optimized decisions inside PaperPortfolio only; it has no broker or real-order integration."""

    def run(
        self,
        cycle: PortfolioResearchCycle,
        portfolio_service: PortfolioService,
        config: AITraderConfig,
    ) -> PaperStrategyCycleResult:
        config.validate()
        portfolio = portfolio_service.portfolio
        prices = {symbol: float(state.analysis.price) for symbol, state in cycle.states.items()}
        ranked = OpportunityRanker().rank(cycle, min_confidence=config.min_confidence)
        optimized = PortfolioOptimizer().optimize(cycle, ranked, portfolio, prices, config)
        optimized_by_symbol = {item.symbol: item for item in optimized}
        correlation_matrix = build_return_correlation_matrix(cycle)

        exits = [symbol for symbol, state in cycle.states.items() if str(state.analysis.signal.action) == "Sell"]
        optimized_entries = [item.symbol for item in optimized if item.target_entry_pct > 0 and item.symbol not in exits]
        remaining = [item.symbol for item in ranked if item.symbol not in exits and item.symbol not in optimized_entries]
        evaluation_order = exits + optimized_entries + remaining
        decisions: list[TradeDecision] = []
        planned_entries: list[str] = []
        trader = AITraderService()

        for symbol in evaluation_order:
            state = cycle.states[symbol]
            analysis = state.analysis
            signal = str(analysis.signal.action)
            symbol_config = config
            correlation_to_portfolio = 0.0
            if signal == "Buy":
                optimized_entry = optimized_by_symbol.get(symbol)
                if state.target_weight <= 0:
                    decisions.append(
                        TradeDecision(
                            symbol=symbol,
                            signal=signal,
                            decision="REJECT",
                            quantity=0,
                            price=float(analysis.price),
                            confidence=float(analysis.signal.confidence),
                            predicted_return=float(analysis.predicted_return),
                            net_edge=float(analysis.signal.net_edge),
                            model_gate_passed=state.model_gate_passed,
                            reason="No enabled portfolio allocation is available for this symbol.",
                            executed=False,
                        )
                    )
                    continue
                if optimized_entry is None or optimized_entry.target_entry_pct <= 0:
                    reason = "Portfolio optimizer assigned no entry budget after risk, sleeve, and correlation constraints."
                    if optimized_entry is not None:
                        reason += f" {optimized_entry.reason}"
                    decisions.append(
                        TradeDecision(
                            symbol=symbol,
                            signal=signal,
                            decision="REJECT",
                            quantity=0,
                            price=float(analysis.price),
                            confidence=float(analysis.signal.confidence),
                            predicted_return=float(analysis.predicted_return),
                            net_edge=float(analysis.signal.net_edge),
                            model_gate_passed=state.model_gate_passed,
                            reason=reason,
                            executed=False,
                        )
                    )
                    continue
                correlation_to_portfolio = candidate_portfolio_correlation(
                    symbol,
                    correlation_matrix,
                    portfolio,
                    additional_symbols=planned_entries,
                )
                symbol_config = replace(
                    config,
                    allocation_pct=max(0.1, min(optimized_entry.target_entry_pct, state.target_weight)),
                    risk_limits=replace(
                        config.risk_limits,
                        max_position_pct=max(0.1, min(config.risk_limits.max_position_pct, state.target_weight)),
                    ),
                )

            decision = trader.evaluate_symbol(
                analysis,
                state.model_gate_passed,
                portfolio,
                symbol_config,
                prices=prices,
                orders=portfolio_service.store.orders(),
                correlation_to_portfolio=correlation_to_portfolio,
            )
            if decision.decision == "BUY" and decision.quantity > 0:
                planned_entries.append(symbol)
            if config.mode == TraderMode.PAPER_AUTO and decision.decision in {"BUY", "SELL"} and decision.quantity > 0:
                portfolio_service.execute(
                    symbol,
                    decision.decision.lower(),
                    decision.quantity,
                    decision.price,
                    reason="ai_trader",
                )
                decision = TradeDecision(
                    **{
                        **decision.__dict__,
                        "executed": True,
                        "reason": decision.reason + " Simulated paper order executed.",
                    }
                )
            decisions.append(decision)

        return PaperStrategyCycleResult(
            decisions=decisions,
            ranked_opportunities=ranked,
            optimized_opportunities=optimized,
        )
