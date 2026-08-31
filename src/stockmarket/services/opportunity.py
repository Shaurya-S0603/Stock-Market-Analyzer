from __future__ import annotations

from dataclasses import dataclass

from .portfolio_cycle import PortfolioResearchCycle


@dataclass(frozen=True)
class RankedOpportunity:
    rank: int
    symbol: str
    eligible: bool
    signal: str
    confidence: float
    predicted_return: float
    net_edge: float
    model_gate_passed: bool
    target_weight: float
    reason: str


class OpportunityRanker:
    """Ranks simulated entry opportunities without placing or sizing orders."""

    def rank(self, cycle: PortfolioResearchCycle, min_confidence: float = 0.65) -> list[RankedOpportunity]:
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")

        prepared: list[tuple[tuple, dict]] = []
        for symbol, state in cycle.states.items():
            analysis = state.analysis
            signal = str(analysis.signal.action)
            confidence = float(analysis.signal.confidence)
            predicted_return = float(analysis.predicted_return)
            net_edge = float(analysis.signal.net_edge)
            reasons: list[str] = []
            if signal != "Buy":
                reasons.append(f"Signal is {signal}, not Buy.")
            if not state.model_gate_passed:
                reasons.append("Model evidence gate failed.")
            if confidence < min_confidence:
                reasons.append(f"Confidence {confidence:.0%} is below {min_confidence:.0%}.")
            if net_edge <= 0:
                reasons.append("Cost-adjusted net edge is not positive.")
            if state.target_weight <= 0:
                reasons.append("No enabled portfolio allocation.")
            eligible = not reasons
            reason = "Eligible simulated entry candidate." if eligible else " ".join(reasons)
            # Eligibility is the primary key. Within eligible candidates, prioritize
            # cost-adjusted edge, then confidence, then raw forecast return.
            sort_key = (
                int(eligible),
                net_edge if eligible else float("-inf"),
                confidence if eligible else 0.0,
                predicted_return if eligible else float("-inf"),
                symbol,
            )
            prepared.append((sort_key, {
                "symbol": symbol,
                "eligible": eligible,
                "signal": signal,
                "confidence": confidence,
                "predicted_return": predicted_return,
                "net_edge": net_edge,
                "model_gate_passed": state.model_gate_passed,
                "target_weight": float(state.target_weight),
                "reason": reason,
            }))

        prepared.sort(key=lambda item: item[0], reverse=True)
        return [RankedOpportunity(rank=index + 1, **payload) for index, (_, payload) in enumerate(prepared)]
