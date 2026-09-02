from __future__ import annotations

from dataclasses import dataclass

from .ai_trader import required_entry_confidence
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
    required_confidence: float = 0.58
    evidence_tier: str = "strong"


class OpportunityRanker:
    """Ranks simulated entry opportunities without placing or sizing orders."""

    def rank(self, cycle: PortfolioResearchCycle, min_confidence: float = 0.58) -> list[RankedOpportunity]:
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")

        prepared: list[tuple[tuple, dict]] = []
        for symbol, state in cycle.states.items():
            analysis = state.analysis
            signal = str(analysis.signal.action)
            confidence = float(analysis.signal.confidence)
            predicted_return = float(analysis.predicted_return)
            net_edge = float(analysis.signal.net_edge)
            entry_threshold = float(getattr(analysis, "adaptive_buy_threshold", 0.003))
            required_confidence = required_entry_confidence(min_confidence, net_edge, entry_threshold)
            reasons: list[str] = []
            if signal != "Buy":
                reasons.append(f"Signal is {signal}, not Buy.")
            if not state.model_gate_passed:
                reasons.append("Trading evidence is too weak for a new paper entry.")
            if confidence < required_confidence:
                reasons.append(f"Confidence {confidence:.0%} is below edge-adjusted requirement {required_confidence:.0%}.")
            if net_edge <= 0:
                reasons.append("Cost-adjusted net edge is not positive.")
            if state.target_weight <= 0:
                reasons.append("No enabled portfolio allocation.")
            eligible = not reasons
            reason = (
                f"Eligible simulated entry candidate with {state.evidence_tier} evidence."
                if eligible
                else " ".join(reasons)
            )
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
                "required_confidence": float(required_confidence),
                "evidence_tier": str(state.evidence_tier),
            }))

        prepared.sort(key=lambda item: item[0], reverse=True)
        return [RankedOpportunity(rank=index + 1, **payload) for index, (_, payload) in enumerate(prepared)]
