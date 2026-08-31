from __future__ import annotations

from dataclasses import replace
import os

import streamlit as st

from ..services import AITraderConfig, RiskLimits, TraderMode
from ..storage import Store
from .components import callout, kpi_grid, page_header, section_header
from .sidebar import load_settings, parse_watchlist, save_settings
from .trader import save_trader_config


RISK_PROFILES: dict[str, dict[str, float | int]] = {
    "Conservative": {
        "min_confidence": 0.75,
        "max_position_pct": 8.0,
        "max_portfolio_exposure_pct": 50.0,
        "max_open_positions": 5,
        "max_daily_trades": 8,
        "max_daily_loss_pct": 2.0,
        "volatility_target_pct": 1.0,
    },
    "Balanced": {
        "min_confidence": 0.65,
        "max_position_pct": 10.0,
        "max_portfolio_exposure_pct": 60.0,
        "max_open_positions": 6,
        "max_daily_trades": 12,
        "max_daily_loss_pct": 3.0,
        "volatility_target_pct": 1.5,
    },
    "Aggressive": {
        "min_confidence": 0.55,
        "max_position_pct": 15.0,
        "max_portfolio_exposure_pct": 75.0,
        "max_open_positions": 8,
        "max_daily_trades": 18,
        "max_daily_loss_pct": 5.0,
        "volatility_target_pct": 2.0,
    },
}


def equal_allocations(symbols: list[str], cash_reserve_pct: float) -> dict[str, float]:
    if not symbols:
        return {}
    investable = max(0.0, 100.0 - float(cash_reserve_pct))
    weight = round(investable / len(symbols), 2)
    allocations = {symbol: weight for symbol in symbols}
    difference = round(investable - sum(allocations.values()), 2)
    allocations[symbols[-1]] = round(allocations[symbols[-1]] + difference, 2)
    return allocations


def validate_allocations(allocations: dict[str, float], cash_reserve_pct: float) -> tuple[bool, float, str]:
    if not allocations:
        return False, float(cash_reserve_pct), "Add at least one symbol."
    if any(float(weight) < 0.0 for weight in allocations.values()):
        return False, 0.0, "Allocations cannot be negative."
    if any(float(weight) > 100.0 for weight in allocations.values()):
        return False, 0.0, "A symbol allocation cannot exceed 100%."
    if not 0.0 <= float(cash_reserve_pct) <= 100.0:
        return False, 0.0, "Cash reserve must be between 0% and 100%."
    total = float(sum(float(weight) for weight in allocations.values()) + float(cash_reserve_pct))
    if abs(total - 100.0) > 0.01:
        return False, total, f"Portfolio allocation must total 100%; current total is {total:.2f}%."
    return True, total, "Portfolio allocation is valid."


def _profile_store() -> Store:
    if "store" not in st.session_state:
        st.session_state.store = Store(os.getenv("PAPER_DB_PATH", ".data/paper_trading.db"))
    return st.session_state.store


def _risk_config(profile: str, mode: TraderMode, largest_allocation: float) -> AITraderConfig:
    values = RISK_PROFILES.get(profile, RISK_PROFILES["Balanced"])
    return AITraderConfig(
        mode=mode,
        min_confidence=float(values["min_confidence"]),
        allocation_pct=max(0.5, min(25.0, float(largest_allocation))),
        risk_limits=RiskLimits(
            max_position_pct=float(values["max_position_pct"]),
            max_portfolio_exposure_pct=float(values["max_portfolio_exposure_pct"]),
            max_open_positions=int(values["max_open_positions"]),
            max_daily_trades=int(values["max_daily_trades"]),
            max_daily_loss_pct=float(values["max_daily_loss_pct"]),
            volatility_target_pct=float(values["volatility_target_pct"]),
        ),
    )


def _restore_persisted_profile() -> bool:
    profile = _profile_store().portfolio_profile()
    if not profile or not profile.get("allocations"):
        return False
    allocations = {str(symbol): float(weight) for symbol, weight in profile["allocations"].items()}
    symbols = list(allocations)
    settings = load_settings()
    save_settings(replace(settings, watchlist=symbols, starting_cash=float(profile["starting_capital"])))
    try:
        mode = TraderMode(str(profile["trader_mode"]))
    except ValueError:
        mode = TraderMode.OBSERVE
    risk_profile = str(profile.get("risk_profile", "Balanced"))
    save_trader_config(_risk_config(risk_profile, mode, max(allocations.values(), default=5.0)))
    st.session_state.portfolio_setup = {
        "starting_cash": float(profile["starting_capital"]),
        "symbols": symbols,
        "allocations": allocations,
        "cash_reserve_pct": float(profile["cash_target_pct"]),
        "risk_profile": risk_profile,
        "trader_mode": mode.value,
    }
    st.session_state.portfolio_onboarding_complete = True
    return True


def onboarding_complete() -> bool:
    if bool(st.session_state.get("portfolio_onboarding_complete", False)):
        return True
    return _restore_persisted_profile()


def current_portfolio_setup() -> dict:
    setup = st.session_state.get("portfolio_setup", {})
    if isinstance(setup, dict) and setup:
        return setup
    if _restore_persisted_profile():
        return st.session_state.get("portfolio_setup", {})
    return {}


def persist_portfolio_setup(setup: dict) -> None:
    _profile_store().save_portfolio_profile(
        starting_capital=float(setup["starting_cash"]),
        cash_target_pct=float(setup["cash_reserve_pct"]),
        risk_profile=str(setup["risk_profile"]),
        trader_mode=str(setup["trader_mode"]),
        allocations={str(symbol): float(weight) for symbol, weight in setup["allocations"].items()},
    )


def clear_portfolio_setup() -> None:
    _profile_store().clear_portfolio_profile()
    for key in (
        "portfolio_setup",
        "portfolio_onboarding_complete",
        "portfolio",
        "portfolio_config",
        "ai_trader_auto_fingerprint",
    ):
        st.session_state.pop(key, None)


def render_onboarding() -> None:
    settings = load_settings()
    page_header(
        "Build your paper portfolio",
        "Define the symbols the strategy may evaluate and the maximum share of paper equity each symbol may use. Allocations are capital ceilings, not automatic purchases.",
        eyebrow="PORTFOLIO ONBOARDING",
        meta="Step 1 of v0.5 Portfolio Intelligence",
    )
    callout(
        "Simulation boundary",
        "This setup controls a paper-trading simulator only. It does not connect to a broker, deposit money, or place real orders.",
    )

    section_header("1 · Account", "Choose the simulated starting equity")
    starting_cash = st.number_input(
        "Starting paper capital",
        min_value=1_000.0,
        max_value=10_000_000.0,
        value=float(settings.starting_cash),
        step=5_000.0,
        help="This is simulated capital used by PaperPortfolio.",
    )

    section_header("2 · Portfolio universe", "Choose 1–20 symbols for the strategy to evaluate")
    raw_symbols = st.text_input(
        "Symbols",
        value=", ".join(settings.watchlist or ["MSFT", "AAPL", "GOOGL", "NVDA", "AMZN"]),
        help="Comma-separated Yahoo Finance symbols. No security is added automatically as an investment recommendation.",
    )
    parsed_symbols = parse_watchlist(raw_symbols)
    symbols = parsed_symbols[:20]
    if len(parsed_symbols) > 20:
        st.warning("The first 20 unique symbols will be used.")

    section_header("3 · Allocation", "Set capital ceilings while preserving an explicit cash reserve")
    controls = st.columns(2)
    cash_reserve_pct = controls[0].slider("Cash reserve (%)", 0.0, 80.0, 20.0, 1.0)
    allocation_style = controls[1].selectbox("Allocation method", ["Equal Weight", "Custom"])
    equal = equal_allocations(symbols, cash_reserve_pct)
    allocations: dict[str, float] = {}
    if allocation_style == "Equal Weight":
        allocations = equal
        st.dataframe(
            [{"Symbol": symbol, "Target ceiling (%)": weight} for symbol, weight in allocations.items()],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("Custom weights plus cash reserve must total exactly 100%.")
        columns = st.columns(2)
        for index, symbol in enumerate(symbols):
            allocations[symbol] = float(
                columns[index % 2].number_input(
                    f"{symbol} ceiling (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(equal.get(symbol, 0.0)),
                    step=1.0,
                    key=f"onboarding_allocation_{symbol}",
                )
            )

    valid, total, message = validate_allocations(allocations, cash_reserve_pct)
    largest = max(allocations.values(), default=0.0)
    kpi_grid([
        {"label": "Symbols", "value": str(len(symbols)), "delta": "Strategy universe", "tone": "blue", "icon": "#"},
        {"label": "Investable ceiling", "value": f"{sum(allocations.values()):.1f}%", "delta": "Across selected symbols", "tone": "blue", "icon": "◫"},
        {"label": "Cash reserve", "value": f"{cash_reserve_pct:.1f}%", "delta": "Unallocated paper equity", "tone": "blue", "icon": "$"},
        {"label": "Allocation total", "value": f"{total:.1f}%", "delta": "Ready" if valid else "Needs adjustment", "tone": "positive" if valid else "warning", "icon": "✓" if valid else "!"},
    ])
    if valid:
        st.success(message)
    else:
        st.warning(message)

    section_header("4 · Trading profile", "Choose how selective the simulator should be")
    profile_cols = st.columns(2)
    risk_profile = profile_cols[0].selectbox("Risk profile", list(RISK_PROFILES), index=1)
    mode_label = profile_cols[1].selectbox(
        "AI Trader startup mode",
        ["Observe", "Paper Auto"],
        index=0,
        help="Observe records decisions without fills. Paper Auto may execute simulated orders only.",
    )
    mode = TraderMode.OBSERVE if mode_label == "Observe" else TraderMode.PAPER_AUTO
    risk_values = RISK_PROFILES[risk_profile]
    st.caption(
        f"{risk_profile}: minimum confidence {float(risk_values['min_confidence']):.0%}, "
        f"portfolio exposure cap {float(risk_values['max_portfolio_exposure_pct']):.0f}%, "
        f"daily realized-loss stop {float(risk_values['max_daily_loss_pct']):.1f}%."
    )

    section_header("5 · Review", "Launch the simulator with these portfolio rules")
    launch = st.button(
        "Launch Portfolio Intelligence",
        type="primary",
        use_container_width=True,
        disabled=not valid,
    )
    if not launch:
        return

    setup = {
        "starting_cash": float(starting_cash),
        "symbols": symbols,
        "allocations": {symbol: float(weight) for symbol, weight in allocations.items()},
        "cash_reserve_pct": float(cash_reserve_pct),
        "risk_profile": risk_profile,
        "trader_mode": mode.value,
    }
    st.session_state.portfolio_setup = setup
    persist_portfolio_setup(setup)
    save_settings(replace(settings, watchlist=symbols, starting_cash=float(starting_cash)))
    save_trader_config(_risk_config(risk_profile, mode, largest))
    st.session_state.portfolio_onboarding_complete = True
    st.session_state.pop("portfolio", None)
    st.session_state.pop("portfolio_config", None)
    st.rerun()
