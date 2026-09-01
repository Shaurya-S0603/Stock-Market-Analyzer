from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..trading import PaperPortfolio
from .ai_trader import AITraderConfig
from .correlation import build_return_correlation_matrix, candidate_portfolio_correlation
from .opportunity import RankedOpportunity
from .portfolio_cycle import PortfolioResearchCycle


@dataclass(frozen=True)
class OptimizedOpportunity:
    symbol: str
    score: float
    target_entry_pct: float
    sleeve_capacity_pct: float
    current_weight_pct: float
    confidence: float
    net_edge: float
    volatility_pct: float
    reason: str
    max_correlation: float = 0.0
    correlation_adjustment: float = 1.0


def _latest_context(analysis) -> dict:
    """Return the latest research context when available, otherwise neutral defaults."""
    live_features = getattr(analysis, "live_features", None)
    if isinstance(live_features, pd.DataFrame) and not live_features.empty:
        return live_features.iloc[-1].to_dict()
    return {}


class PortfolioOptimizer:
    """Allocates a simulated entry budget across already-eligible opportunities."""

    def optimize(
        self,
        cycle: PortfolioResearchCycle,
        ranked: list[RankedOpportunity],
        portfolio: PaperPortfolio,
        prices: dict[str, float],
        config: AITraderConfig,
    ) -> list[OptimizedOpportunity]:
        config.validate()
        equity = portfolio.equity(prices)
        if equity <= 0:
            return []
        current_values = {
            symbol: position.quantity * prices.get(symbol, position.average_cost)
            for symbol, position in portfolio.positions.items()
            if position.quantity > 0
        }
        current_exposure_pct = sum(current_values.values()) / equity * 100.0
        cash_pct = portfolio.cash / equity * 100.0
        exposure_room_pct = max(config.risk_limits.max_portfolio_exposure_pct - current_exposure_pct, 0.0)
        cycle_budget_pct = max(min(cash_pct, exposure_room_pct), 0.0)
        correlation_matrix = build_return_correlation_matrix(cycle)

        prepared: list[tuple[RankedOpportunity, float, float, float, float, float, float]] = []
        for item in ranked:
            if not item.eligible or item.symbol not in cycle.states:
                continue
            state = cycle.states[item.symbol]
            current_weight = current_values.get(item.symbol, 0.0) / equity * 100.0
            sleeve_capacity = max(float(state.target_weight) - current_weight, 0.0)
            if sleeve_capacity <= 0:
                continue
            latest = _latest_context(state.analysis)
            raw_volatility = latest.get("context_volatility_20", latest.get("volatility_10", 0.01))
            try:
                volatility_pct = max(abs(float(raw_volatility)) * 100.0, 0.05)
            except (TypeError, ValueError):
                volatility_pct = 1.0
            confidence = float(item.confidence)
            edge = max(float(item.net_edge), 0.0)
            max_correlation = candidate_portfolio_correlation(item.symbol, correlation_matrix, portfolio)
            if max_correlation <= 0.5:
                correlation_adjustment = 1.0
            else:
                scaled = min((max_correlation - 0.5) / 0.5, 1.0)
                correlation_adjustment = max(
                    config.risk_limits.correlation_penalty_floor,
                    1.0 - scaled * (1.0 - config.risk_limits.correlation_penalty_floor),
                )
            risk_adjusted_edge = edge * max(confidence, 0.01) / volatility_pct
            regime_penalty = 0.85 if float(latest.get("regime_high_volatility", 0.0) or 0.0) >= 0.5 else 1.0
            score = max(risk_adjusted_edge * regime_penalty * correlation_adjustment, 1e-12)
            prepared.append((item, score, sleeve_capacity, current_weight, volatility_pct, max_correlation, correlation_adjustment))

        total_score = sum(row[1] for row in prepared)
        optimized: list[OptimizedOpportunity] = []
        for item, score, sleeve_capacity, current_weight, volatility_pct, max_correlation, correlation_adjustment in prepared:
            proportional_budget = cycle_budget_pct * score / total_score if total_score > 0 else 0.0
            per_entry_cap = min(float(config.allocation_pct), float(config.risk_limits.max_position_pct), sleeve_capacity)
            target_entry_pct = min(proportional_budget, per_entry_cap)
            if max_correlation > config.risk_limits.max_pairwise_correlation:
                target_entry_pct = 0.0
            optimized.append(
                OptimizedOpportunity(
                    symbol=item.symbol,
                    score=float(score),
                    target_entry_pct=float(max(target_entry_pct, 0.0)),
                    sleeve_capacity_pct=float(sleeve_capacity),
                    current_weight_pct=float(current_weight),
                    confidence=float(item.confidence),
                    net_edge=float(item.net_edge),
                    volatility_pct=float(volatility_pct),
                    reason=(
                        f"Risk-adjusted edge score {score:.6f}; sleeve room {sleeve_capacity:.2f}%; "
                        f"cycle budget {cycle_budget_pct:.2f}%; max portfolio correlation {max_correlation:.2f}."
                    ),
                    max_correlation=float(max_correlation),
                    correlation_adjustment=float(correlation_adjustment),
                )
            )
        optimized.sort(key=lambda row: (row.target_entry_pct > 0, row.score, row.symbol), reverse=True)
        return optimized
