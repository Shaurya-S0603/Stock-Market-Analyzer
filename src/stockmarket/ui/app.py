from __future__ import annotations

import streamlit as st

from .context import build_context
from .sidebar import load_settings, render_sidebar_shell
from .site_pages import ai_trader_page, backtesting_page, dashboard_page, markets_page, model_analytics_page, portfolio_page, risk_analytics_page, settings_page, trade_journal_page
from .theme import apply_theme


def render_app() -> None:
    apply_theme()
    settings = load_settings()
    ctx = build_context(settings)
    pages = {
        "Workspace": [
            st.Page(lambda: dashboard_page(ctx), title="Dashboard", icon=":material/dashboard:", default=True),
            st.Page(lambda: markets_page(ctx), title="Markets", icon=":material/candlestick_chart:"),
            st.Page(lambda: ai_trader_page(ctx), title="AI Trader", icon=":material/smart_toy:"),
            st.Page(lambda: portfolio_page(ctx), title="Portfolio", icon=":material/account_balance_wallet:"),
            st.Page(lambda: trade_journal_page(ctx), title="Trade Journal", icon=":material/receipt_long:"),
        ],
        "Research": [
            st.Page(lambda: model_analytics_page(ctx), title="Model Analytics", icon=":material/model_training:"),
            st.Page(lambda: backtesting_page(ctx), title="Backtesting", icon=":material/query_stats:"),
            st.Page(lambda: risk_analytics_page(ctx), title="Risk Analytics", icon=":material/security:"),
        ],
        "System": [st.Page(lambda: settings_page(ctx), title="Settings", icon=":material/settings:")],
    }
    navigation = st.navigation(pages, position="sidebar", expanded=True)
    render_sidebar_shell(settings)
    navigation.run()
