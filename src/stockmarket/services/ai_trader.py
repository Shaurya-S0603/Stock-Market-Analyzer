from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..trading import PaperPortfolio
from .analysis import SymbolAnalysis
from .portfolio import PortfolioService
from .risk import RiskEngine, RiskLimits


class TraderMode(StrEnum):
    OFF = "OFF"
    OBSERVE = "OBSERVE"
    PAPER_AUTO = "PAPER_AUTO"


@dataclass(frozen=True)
class AITraderConfig:
    mode: TraderMode = TraderMode.OFF
    min_confidence: float = 0.65
    allocation_pct: float = 5.0
    risk_limits: RiskLimits = RiskLimits()

    def validate(self) -> None:
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if not 0.1 <= self.allocation_pct <= 100.0:
            raise ValueError("allocation_pct must be between 0.1 and 100")
        self.risk_limits.validate()


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


def cycle_fingerprint(analyses: dict[str, SymbolAnalysis], config: AITraderConfig) -> tuple:
    """Stable signature used to avoid re-evaluating the same market bars in active-session automation."""
    config.validate()
    market = tuple(
        sorted(
            (
                symbol.upper(),
                str(analysis.timestamp),
                analysis.signal.action,
                round(float(analysis.predicted_return), 10),
            )
            for symbol, analysis in analyses.items()
        )
    )
    limits = config.risk_limits
    settings = (
        config.mode.value,
        round(config.min_confidence, 6),
        round(config.allocation_pct, 6),
        round(limits.max_position_pct, 6),
        round(limits.max_portfolio_exposure_pct, 6),
        limits.max_open_positions,
        limits.max_daily_trades,
        round(limits.max_daily_loss_pct, 6),
        round(limits.volatility_target_pct, 6),
        round(limits.max_pairwise_correlation, 6),
        round(limits.correlation_penalty_floor, 6),
    )
    return market + (settings,)


class AITraderService:
    """Evaluates model signals and optionally routes approved actions to the paper portfolio only."""

    def evaluate_symbol(
        self,
        analysis: SymbolAnalysis,
        model_gate_passed: bool,
        portfolio: PaperPortfolio,
        config: AITraderConfig,
        prices: dict[str, float] | None = None,
        orders: list[dict] | None = None,
        correlation_to_portfolio: float = 0.0,
    ) -> TradeDecision:
        config.validate()
        symbol = analysis.symbol.upper()
        signal = analysis.signal.action
        confidence = float(analysis.signal.confidence)
        position = portfolio.positions.get(symbol)
        position_qty = position.quantity if position else 0

        base = dict(
            symbol=symbol,
            signal=signal,
            price=float(analysis.price),
            confidence=confidence,
            predicted_return=float(analysis.predicted_return),
            net_edge=float(analysis.signal.net_edge),
            model_gate_passed=bool(model_gate_passed),
            executed=False,
        )

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
            latest = analysis.live_features.iloc[-1] if hasattr(analysis, "live_features") else None
            volatility = float(latest.get("volatility_10", 0.01)) if latest is not None else 0.01
            assessment = RiskEngine().assess_entry(
                symbol,
                float(analysis.price),
                confidence,
                volatility,
                portfolio,
                prices or {symbol: float(analysis.price)},
                orders or [],
                config.allocation_pct,
                config.risk_limits,
                correlation_to_portfolio=correlation_to_portfolio,
            )
            if not assessment.approved:
                return TradeDecision(decision="REJECT", quantity=0, reason=assessment.reason, **base)
            return TradeDecision(
                decision="BUY",
                quantity=assessment.quantity,
                reason=(
                    f"Signal and model gates passed. {assessment.reason} "
                    f"Correlation adjustment {assessment.correlation_adjustment:.2f}."
                ),
                **base,
            )

        if signal == "Sell":
            if position_qty <= 0:
                return TradeDecision(decision="REJECT", quantity=0, reason="Sell signal ignored because no long paper position is open.", **base)
            return TradeDecision(decision="SELL", quantity=position_qty, reason="Exit signal, confidence, and model evidence gates passed.", **base)

        return TradeDecision(decision="HOLD", quantity=0, reason="Unsupported signal was treated as hold.", **base)

    def run_cycle(
        self,
        analyses: dict[str, SymbolAnalysis],
        model_gates: dict[str, bool],
        portfolio: PaperPortfolio,
        portfolio_service: PortfolioService,
        config: AITraderConfig,
    ) -> list[TradeDecision]:
        config.validate()
        decisions: list[TradeDecision] = []
        prices = {symbol: float(analysis.price) for symbol, analysis in analyses.items()}
        orders = portfolio_service.store.orders()
        for symbol, analysis in analyses.items():
            decision = self.evaluate_symbol(analysis, model_gates.get(symbol, False), portfolio, config, prices, orders)
            if config.mode == TraderMode.PAPER_AUTO and decision.decision in {"BUY", "SELL"} and decision.quantity > 0:
                side = decision.decision.lower()
                portfolio_service.execute(symbol, side, decision.quantity, decision.price, reason="ai_trader")
                decision = TradeDecision(**{**decision.__dict__, "executed": True, "reason": decision.reason + " Paper order executed."})
            decisions.append(decision)
        return decisions
