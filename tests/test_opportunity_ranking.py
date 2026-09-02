from types import SimpleNamespace

from stockmarket.services.opportunity import OpportunityRanker
from stockmarket.services.portfolio_cycle import PortfolioResearchCycle, PortfolioSignalState


def _state(symbol: str, edge: float, confidence: float, gate: bool = True, target: float = 20.0, signal: str = "Buy"):
    analysis = SimpleNamespace(
        symbol=symbol,
        predicted_return=edge + 0.002,
        signal=SimpleNamespace(action=signal, confidence=confidence, net_edge=edge),
        adaptive_buy_threshold=0.003,
    )
    return PortfolioSignalState(symbol, analysis, gate, "gate", target)


def test_ranker_prioritizes_eligible_edge_then_confidence() -> None:
    cycle = PortfolioResearchCycle(
        states={
            "AAPL": _state("AAPL", 0.010, 0.80),
            "NVDA": _state("NVDA", 0.014, 0.72),
            "MSFT": _state("MSFT", 0.020, 0.90, gate=False),
            "GOOGL": _state("GOOGL", 0.008, 0.60),
            "AMZN": _state("AMZN", 0.003, 0.60),
        },
        unavailable={},
    )
    ranked = OpportunityRanker().rank(cycle, min_confidence=0.65)
    assert [item.symbol for item in ranked[:3]] == ["NVDA", "AAPL", "GOOGL"]
    assert all(item.eligible for item in ranked[:3])
    assert not ranked[3].eligible and not ranked[4].eligible
    assert {ranked[3].symbol, ranked[4].symbol} == {"MSFT", "AMZN"}


def test_ranker_rejects_symbols_without_allocation() -> None:
    cycle = PortfolioResearchCycle(states={"AAPL": _state("AAPL", 0.02, 0.9, target=0.0)}, unavailable={})
    ranked = OpportunityRanker().rank(cycle)
    assert not ranked[0].eligible
    assert "allocation" in ranked[0].reason.lower()
