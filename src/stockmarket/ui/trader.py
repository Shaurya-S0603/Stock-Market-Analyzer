from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from ..services import AITraderConfig, AITraderService, TraderMode
from .context import AppContext


def load_trader_config() -> AITraderConfig:
    stored = st.session_state.get("ai_trader_config", {})
    try:
        mode = TraderMode(stored.get("mode", TraderMode.OFF))
    except ValueError:
        mode = TraderMode.OFF
    return AITraderConfig(mode=mode, min_confidence=float(stored.get("min_confidence", 0.65)), allocation_pct=float(stored.get("allocation_pct", 5.0)))


def save_trader_config(config: AITraderConfig) -> None:
    config.validate()
    data = asdict(config)
    data["mode"] = config.mode.value
    st.session_state.ai_trader_config = data


def run_trader_cycle(ctx: AppContext, config: AITraderConfig) -> list:
    result = ctx.analyze_watchlist()
    if not result.available:
        return []
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
    frame = pd.DataFrame(normalized)
    return frame.rename(columns={"symbol":"Symbol", "signal":"Signal", "decision":"Decision", "quantity":"Qty", "price":"Price", "confidence":"Confidence", "predicted_return":"Predicted Return", "net_edge":"Net Edge", "model_gate_passed":"Model Gate", "reason":"Reason", "executed":"Executed"})
