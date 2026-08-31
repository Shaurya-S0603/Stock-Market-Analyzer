from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..trading import PaperPortfolio
from .analysis import SymbolAnalysis
from .portfolio import PortfolioService


class TraderMode(StrEnum):
    OFF = "OFF"
    OBSERVE = "OBSERVE"
    PAPER_AUTO = "PAPER_AUTO"


@dataclass(frozen=True)
class AITraderConfig:
    mode: TraderMode = TraderMode.OFF
    min_confidence: float = 0.65
    allocation_pct: float = 5.0

    def validate(self) -> None:
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if not 0.1 <= self.allocation_pct <= 100.0:
            raise ValueError("allocation_pct must be between 0.1 and 100")


@dataclass(frozen=True)
class TradeDecision:
    symbol: str
    signal: str
    decision: str
    quantity: int
    price: float
    confidence: float
    predicted_return: float
    net_edge: float
    model_gate_passed: bool
    reason: str
    executed: bool = False


class AITraderService:
    """Evaluates model signals and optionally routes approved actions to the paper portfolio only."""

    def evaluate_symbol(self, analysis: SymbolAnalysis, model_gate_passed: bool, portfolio: PaperPortfolio, config: AITraderConfig) -> TradeDecision:
        config.validate()
        symbol = analysis.symbol.upper()
        signal = analysis.signal.action
        confidence = float(analysis.signal.confidence)
        position = portfolio.positions.get(symbol)
        position_qty = position.quantity if position else 0
        base = dict(symbol=symbol, signal=signal, price=float(analysis.price), confidence=confidence, predicted_return=float(analysis.predicted_return), net_edge=float(analysis.signal.net_edge), model_gate_passed=bool(model_gate_passed), executed=False)
        if config.mode == TraderMode.OFF:
            return TradeDecision(decision="OFF", quantity=0, reason="AI Trader is disabled.", **base)
        if signal == "Hold":
            return TradeDecision(decision="HOLD", quantity=0, reason="Current signal does not cross an entry or exit threshold.", **base)
        if not model_gate_passed:
            return TradeDecision(decision="REJECT", quantity=0, reason="Model evidence gate did not pass for this symbol.", **base)
        if confidence < config.min_confidence:
            return TradeDecision(decision="REJECT", quantity=0, reason=f"Signal confidence {confidence:.0%} is below the {config.min_confidence:.0%} minimum.", **base)
        if signal == "Buy":
            if position_qty > 0:
                return TradeDecision(decision="REJECT", quantity=0, reason="An open paper position already exists for this symbol.", **base)
            budget = portfolio.cash * (config.allocation_pct / 100.0)
            estimated_unit_cost = analysis.price * (1.0 + portfolio.slippage_rate) * (1.0 + portfolio.commission_rate)
            quantity = int(budget / estimated_unit_cost) if estimated_unit_cost > 0 else 0
            if quantity < 1:
                return TradeDecision(decision="REJECT", quantity=0, reason="Available paper cash is insufficient for the configured allocation.", **base)
            return TradeDecision(decision="BUY", quantity=quantity, reason="Signal, confidence, and model evidence gates passed.", **base)
        if signal == "Sell":
            if position_qty <= 0:
                return TradeDecision(decision="REJECT", quantity=0, reason="Sell signal ignored because no long paper position is open.", **base)
            return TradeDecision(decision="SELL", quantity=position_qty, reason="Exit signal, confidence, and model evidence gates passed.", **base)
        return TradeDecision(decision="HOLD", quantity=0, reason="Unsupported signal was treated as hold.", **base)

    def run_cycle(self, analyses: dict[str, SymbolAnalysis], model_gates: dict[str, bool], portfolio: PaperPortfolio, portfolio_service: PortfolioService, config: AITraderConfig) -> list[TradeDecision]:
        config.validate()
        decisions: list[TradeDecision] = []
        for symbol, analysis in analyses.items():
            decision = self.evaluate_symbol(analysis, model_gates.get(symbol, False), portfolio, config)
            if config.mode == TraderMode.PAPER_AUTO and decision.decision in {"BUY", "SELL"} and decision.quantity > 0:
                portfolio_service.execute(symbol, decision.decision.lower(), decision.quantity, decision.price, reason="ai_trader")
                decision = TradeDecision(**{**decision.__dict__, "executed": True, "reason": decision.reason + " Paper order executed."})
            decisions.append(decision)
        return decisions
