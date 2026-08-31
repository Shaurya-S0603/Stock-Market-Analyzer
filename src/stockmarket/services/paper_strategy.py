from __future__ import annotations

from dataclasses import dataclass, replace

from .ai_trader import AITraderConfig, AITraderService, TradeDecision, TraderMode
from .opportunity import OpportunityRanker, RankedOpportunity
from .portfolio import PortfolioService
from .portfolio_cycle import PortfolioResearchCycle


@dataclass
class PaperStrategyCycleResult:
    decisions: list[TradeDecision]
    ranked_opportunities: list[RankedOpportunity]


class PaperOnlyPortfolioStrategy:
    """Coordinates ranked decisions inside PaperPortfolio only; it has no broker or real-order integration."""

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
        exits = [
            symbol
            for symbol, state in cycle.states.items()
            if str(state.analysis.signal.action) == "Sell"
        ]
        remaining = [item.symbol for item in ranked if item.symbol not in exits]
        evaluation_order = exits + remaining
        decisions: list[TradeDecision] = []
        trader = AITraderService()

        for symbol in evaluation_order:
            state = cycle.states[symbol]
            analysis = state.analysis
            signal = str(analysis.signal.action)
            symbol_config = config
            if signal == "Buy":
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
                symbol_config = replace(
                    config,
                    allocation_pct=max(0.1, min(config.allocation_pct, state.target_weight)),
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
            )
            if (
                config.mode == TraderMode.PAPER_AUTO
                and decision.decision in {"BUY", "SELL"}
                and decision.quantity > 0
            ):
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

        return PaperStrategyCycleResult(decisions=decisions, ranked_opportunities=ranked)
