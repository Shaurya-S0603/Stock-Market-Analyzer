from __future__ import annotations

import streamlit as st

from ..services import TraderMode
from .context import build_context
from .onboarding import onboarding_complete, render_onboarding
from .research_lab import research_lab_page
from .sidebar import load_settings, render_sidebar_shell
from .site_pages import (
    ai_trader_page,
    backtesting_page,
    dashboard_page,
    markets_page,
    model_analytics_page,
    portfolio_page,
    risk_analytics_page,
    settings_page,
    trade_journal_page,
)
from .theme import apply_theme
from .trader import load_trader_config, run_auto_trader_tick


@st.fragment(run_every="120s")
def _paper_auto_heartbeat(ctx) -> None:
    config = load_trader_config()
    if config.mode != TraderMode.PAPER_AUTO:
        return
    try:
        decisions, status = run_auto_trader_tick(ctx, config)
    except (RuntimeError, ValueError) as exc:
        st.warning(f"Paper-auto check skipped: {exc}")
        return
    if status == "executed":
        fills = sum(1 for decision in decisions if decision.executed)
        st.caption(f"PAPER AUTO checked new market bars · {fills} simulated fill(s).")
    elif status == "unchanged":
        st.caption("PAPER AUTO active · waiting for a new market bar.")


def _build_navigation_pages(ctx):
    """Build pages with stable, explicit URL paths."""
    return {
        "Workspace": [
            st.Page(
                lambda: dashboard_page(ctx),
                title="Dashboard",
                icon=":material/dashboard:",
                default=True,
            ),
            st.Page(
                lambda: markets_page(ctx),
                title="Markets",
                icon=":material/candlestick_chart:",
                url_path="markets",
            ),
            st.Page(
                lambda: ai_trader_page(ctx),
                title="AI Trader",
                icon=":material/smart_toy:",
                url_path="ai-trader",
            ),
            st.Page(
                lambda: portfolio_page(ctx),
                title="Portfolio",
                icon=":material/account_balance_wallet:",
                url_path="portfolio",
            ),
            st.Page(
                lambda: trade_journal_page(ctx),
                title="Trade Journal",
                icon=":material/receipt_long:",
                url_path="trade-journal",
            ),
        ],
        "Research": [
            st.Page(
                lambda: model_analytics_page(ctx),
                title="Model Analytics",
                icon=":material/model_training:",
                url_path="model-analytics",
            ),
            st.Page(
                lambda: research_lab_page(ctx),
                title="Research Lab",
                icon=":material/science:",
                url_path="research-lab",
            ),
            st.Page(
                lambda: backtesting_page(ctx),
                title="Backtesting",
                icon=":material/query_stats:",
                url_path="backtesting",
            ),
            st.Page(
                lambda: risk_analytics_page(ctx),
                title="Risk Analytics",
                icon=":material/security:",
                url_path="risk-analytics",
            ),
        ],
        "System": [
            st.Page(
                lambda: settings_page(ctx),
                title="Settings",
                icon=":material/settings:",
                url_path="settings",
            ),
        ],
    }


def render_app() -> None:
    apply_theme()
    if not onboarding_complete():
        render_onboarding()
        return

    settings = load_settings()
    ctx = build_context(settings)

    navigation = st.navigation(_build_navigation_pages(ctx), position="sidebar", expanded=True)
    render_sidebar_shell(settings)
    with st.sidebar:
        _paper_auto_heartbeat(ctx)
    navigation.run()
