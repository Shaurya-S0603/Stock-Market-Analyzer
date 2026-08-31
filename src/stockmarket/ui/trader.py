from __future__ import annotations

import pandas as pd
import streamlit as st

from ..services import AITraderConfig, AITraderService, RiskLimits, RiskPolicy, TraderMode
from .context import AppContext


def load_trader_config() -> AITraderConfig:
    stored = st.session_state.get("ai_trader_config", {})
    try:
        mode = TraderMode(stored.get("mode", TraderMode.OFF))
    except ValueError:
        mode = TraderMode.OFF
    risk_data = stored.get("risk_limits", {}) if isinstance(stored.get("risk_limits", {}), dict) else {}
    return AITraderConfig(mode=mode, min_confidence=float(stored.get("min_confidence", 0.65)), allocation_pct=float(stored.get("allocation_pct", 5.0)), risk_limits=RiskLimits(max_position_pct=float(risk_data.get("max_position_pct", 10.0)), max_portfolio_exposure_pct=float(risk_data.get("max_portfolio_exposure_pct", 60.0)), max_open_positions=int(risk_data.get("max_open_positions", 6)), max_daily_trades=int(risk_data.get("max_daily_trades", 12)), max_daily_loss_pct=float(risk_data.get("max_daily_loss_pct", 3.0)), volatility_target_pct=float(risk_data.get("volatility_target_pct", 1.5))))


def save_trader_config(config: AITraderConfig) -> None:
    config.validate()
    st.session_state.ai_trader_config = {"mode": config.mode.value, "min_confidence": config.min_confidence, "allocation_pct": config.allocation_pct, "risk_limits": config.risk_limits.__dict__}


def run_trader_cycle(ctx: AppContext, config: AITraderConfig) -> list:
    result = ctx.analyze_watchlist()
    if not result.available:
        return []
    prices = {symbol: analysis.price for symbol, analysis in result.available.items()}
    ctx.portfolio_service.apply_risk_policy(prices, RiskPolicy(ctx.settings.automation_enabled, ctx.settings.stop_loss_pct, ctx.settings.take_profit_pct))
    gates: dict[str, bool] = {}
    for symbol, analysis in result.available.items():
        try:
            _, gate = ctx.analysis_service.benchmark_report(analysis)
            gates[symbol] = bool(gate.approved)
        except ValueError:
            gates[symbol] = False
    decisions = AITraderService().run_cycle(result.available, gates, ctx.portfolio, ctx.portfolio_service, config)
    st.session_state.ai_trader_last_decisions = [decision.__dict__ for decision in decisions]
    return decisions


def decisions_frame(decisions: list | None = None) -> pd.DataFrame:
    rows = decisions if decisions is not None else st.session_state.get("ai_trader_last_decisions", [])
    if not rows:
        return pd.DataFrame()
    normalized = [row.__dict__ if hasattr(row, "__dict__") else row for row in rows]
    return pd.DataFrame(normalized).rename(columns={"symbol":"Symbol", "signal":"Signal", "decision":"Decision", "quantity":"Qty", "price":"Price", "confidence":"Confidence", "predicted_return":"Predicted Return", "net_edge":"Net Edge", "model_gate_passed":"Model Gate", "reason":"Reason", "executed":"Executed"})
