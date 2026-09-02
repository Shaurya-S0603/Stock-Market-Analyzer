from __future__ import annotations

import pandas as pd
import streamlit as st

from ..services import (
    AITraderConfig,
    ExperimentRegistry,
    JournalService,
    PaperOnlyPortfolioStrategy,
    PortfolioCycleService,
    RiskLimits,
    RiskPolicy,
    TraderMode,
    cycle_fingerprint,
    detect_experiment_drift,
)
from .context import AppContext


POLICY_VERSION = 2


def _legacy_default(value, old, new):
    return new if value == old else value


def load_trader_config() -> AITraderConfig:
    stored = st.session_state.get("ai_trader_config", {})
    legacy = isinstance(stored, dict) and int(stored.get("policy_version", 1)) < POLICY_VERSION
    try:
        mode = TraderMode(stored.get("mode", TraderMode.OFF))
    except ValueError:
        mode = TraderMode.OFF
    risk_data = stored.get("risk_limits", {}) if isinstance(stored.get("risk_limits", {}), dict) else {}

    min_confidence = float(stored.get("min_confidence", 0.58))
    allocation_pct = float(stored.get("allocation_pct", 7.5))
    max_position_pct = float(risk_data.get("max_position_pct", 12.0))
    max_exposure_pct = float(risk_data.get("max_portfolio_exposure_pct", 70.0))
    max_positions = int(risk_data.get("max_open_positions", 8))
    max_daily_trades = int(risk_data.get("max_daily_trades", 16))
    volatility_target_pct = float(risk_data.get("volatility_target_pct", 1.75))
    max_pairwise_correlation = float(risk_data.get("max_pairwise_correlation", 0.92))
    correlation_penalty_floor = float(risk_data.get("correlation_penalty_floor", 0.40))

    if legacy:
        min_confidence = float(_legacy_default(min_confidence, 0.65, 0.58))
        allocation_pct = float(_legacy_default(allocation_pct, 5.0, 7.5))
        max_position_pct = float(_legacy_default(max_position_pct, 10.0, 12.0))
        max_exposure_pct = float(_legacy_default(max_exposure_pct, 60.0, 70.0))
        max_positions = int(_legacy_default(max_positions, 6, 8))
        max_daily_trades = int(_legacy_default(max_daily_trades, 12, 16))
        volatility_target_pct = float(_legacy_default(volatility_target_pct, 1.5, 1.75))
        max_pairwise_correlation = float(_legacy_default(max_pairwise_correlation, 0.90, 0.92))
        correlation_penalty_floor = float(_legacy_default(correlation_penalty_floor, 0.35, 0.40))

    return AITraderConfig(
        mode=mode,
        min_confidence=min_confidence,
        allocation_pct=allocation_pct,
        risk_limits=RiskLimits(
            max_position_pct=max_position_pct,
            max_portfolio_exposure_pct=max_exposure_pct,
            max_open_positions=max_positions,
            max_daily_trades=max_daily_trades,
            max_daily_loss_pct=float(risk_data.get("max_daily_loss_pct", 3.0)),
            volatility_target_pct=volatility_target_pct,
            max_pairwise_correlation=max_pairwise_correlation,
            correlation_penalty_floor=correlation_penalty_floor,
        ),
    )


def save_trader_config(config: AITraderConfig) -> None:
    config.validate()
    st.session_state.ai_trader_config = {
        "policy_version": POLICY_VERSION,
        "mode": config.mode.value,
        "min_confidence": config.min_confidence,
        "allocation_pct": config.allocation_pct,
        "risk_limits": config.risk_limits.__dict__,
    }
    st.session_state.pop("ai_trader_auto_fingerprint", None)


def _portfolio_allocations(ctx: AppContext) -> dict[str, float]:
    profile = ctx.store.portfolio_profile()
    if not profile:
        return {}
    return {str(symbol).upper(): float(weight) for symbol, weight in profile.get("allocations", {}).items()}


def _register_experiments(ctx: AppContext, research_cycle) -> tuple[list[dict], list[dict]]:
    registry = ExperimentRegistry(ctx.store.path)
    records: list[dict] = []
    drift_rows: list[dict] = []
    for symbol, state in research_cycle.states.items():
        benchmark: dict = {
            "trading_gate_passed": bool(state.model_gate_passed),
            "trading_gate_reason": state.model_gate_reason,
            "trading_evidence_tier": getattr(state, "evidence_tier", "unknown"),
            "trading_evidence_size_multiplier": float(getattr(state, "evidence_multiplier", 0.0)),
        }
        try:
            _, best = ctx.analysis_service.ensemble_benchmark_report(state.analysis)
            benchmark["best_challenger"] = best
        except ValueError as exc:
            benchmark["challenger_error"] = str(exc)
        record = registry.record(state.analysis, ctx.request, benchmark)
        records.append({"experiment_id": record.experiment_id, "symbol": symbol, "model_hash": record.model_hash, "regime": record.regime})

        history = registry.recent(symbol, limit=10)
        baseline = next((row for row in history if row["experiment_id"] != record.experiment_id), None)
        if baseline is not None:
            current = {
                "metrics": record.metrics,
                "feature_stats": record.feature_stats,
            }
            report = detect_experiment_drift(current, baseline)
            registry.record_drift(record.experiment_id, symbol, report)
            drift_rows.append({"symbol": symbol, "status": report.status, "score": report.score, "reasons": report.reasons})
    return records, drift_rows


def run_trader_cycle(ctx: AppContext, config: AITraderConfig, result=None) -> list:
    result = result or ctx.analyze_watchlist()
    if not result.available:
        return []
    allocations = _portfolio_allocations(ctx)
    prices = {symbol: analysis.price for symbol, analysis in result.available.items()}
    ctx.portfolio_service.apply_adaptive_exit_policy(
        result.available,
        RiskPolicy(ctx.settings.automation_enabled, ctx.settings.stop_loss_pct, ctx.settings.take_profit_pct),
    )
    research_cycle = PortfolioCycleService(ctx.analysis_service).run(
        ctx.settings.watchlist,
        ctx.request,
        allocations,
        watchlist=result,
    )
    experiments, drift_rows = _register_experiments(ctx, research_cycle)
    strategy_result = PaperOnlyPortfolioStrategy().run(research_cycle, ctx.portfolio_service, config)
    decisions = strategy_result.decisions
    cycle = JournalService(ctx.store).record_cycle(decisions, config.mode, ctx.portfolio, prices)
    st.session_state.ai_trader_last_decisions = [decision.__dict__ for decision in decisions]
    st.session_state.ai_trader_last_ranked = [item.__dict__ for item in strategy_result.ranked_opportunities]
    st.session_state.ai_trader_last_optimized = [item.__dict__ for item in strategy_result.optimized_opportunities]
    st.session_state.ai_trader_last_experiments = experiments
    st.session_state.ai_trader_last_drift = drift_rows
    st.session_state.ai_trader_last_cycle = cycle.__dict__
    return decisions


def run_auto_trader_tick(ctx: AppContext, config: AITraderConfig) -> tuple[list, str]:
    """Run at most once per unique market/config/allocation fingerprint while the session is active."""
    if config.mode != TraderMode.PAPER_AUTO:
        return [], "inactive"
    result = ctx.analyze_watchlist()
    if not result.available:
        return [], "no_data"
    allocations = _portfolio_allocations(ctx)
    fingerprint = (
        cycle_fingerprint(result.available, config),
        tuple(sorted((symbol, round(weight, 6)) for symbol, weight in allocations.items())),
    )
    if st.session_state.get("ai_trader_auto_fingerprint") == fingerprint:
        return [], "unchanged"
    decisions = run_trader_cycle(ctx, config, result=result)
    st.session_state.ai_trader_auto_fingerprint = fingerprint
    return decisions, "executed"


def decisions_frame(decisions: list | None = None) -> pd.DataFrame:
    rows = decisions if decisions is not None else st.session_state.get("ai_trader_last_decisions", [])
    if not rows:
        return pd.DataFrame()
    normalized = [row.__dict__ if hasattr(row, "__dict__") else row for row in rows]
    return pd.DataFrame(normalized).rename(columns={
        "symbol":"Symbol", "signal":"Signal", "decision":"Decision", "quantity":"Qty", "price":"Price",
        "confidence":"Confidence", "predicted_return":"Predicted Return", "net_edge":"Net Edge",
        "model_gate_passed":"Model Gate", "reason":"Reason", "executed":"Executed",
    })


def ranked_opportunities_frame() -> pd.DataFrame:
    rows = st.session_state.get("ai_trader_last_ranked", [])
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).rename(columns={
        "rank": "Rank",
        "symbol": "Symbol",
        "eligible": "Eligible",
        "signal": "Signal",
        "confidence": "Confidence",
        "required_confidence": "Required Confidence",
        "predicted_return": "Predicted Return",
        "net_edge": "Net Edge",
        "model_gate_passed": "Model Gate",
        "evidence_tier": "Evidence Tier",
        "target_weight": "Target Weight",
        "reason": "Reason",
    })
