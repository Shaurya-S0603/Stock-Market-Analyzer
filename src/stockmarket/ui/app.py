"""QuantEdge: one focused Streamlit-only personal trading research workspace.

No mandatory onboarding, ML auto-trader, brokerage, external API server,
paid backend, or implicit portfolio rebalancing.
"""
from __future__ import annotations

import streamlit as st

from ..workspace.home import personal_dashboard_page
from ..workspace.ui import market_explorer_page
from ..workspace.pages import chart_terminal_page, stock_research_page, screener_page
from ..workspace.strategy_pages import (
    strategy_builder_page, strategy_backtesting_page, backtest_comparison_page,
)
from ..workspace.monitor_pages import alert_center_page, strategy_paper_page
from ..workspace.manual_page import manual_paper_page
from ..workspace.data_management import data_management_page
from .theme import apply_theme


def navigation_pages():
    """Single consistent sidebar for first-time and returning users."""
    return {
        "Workspace": [
            st.Page(personal_dashboard_page, title="Overview", icon=":material/dashboard:", default=True),
            st.Page(market_explorer_page, title="Market Explorer", icon=":material/search:", url_path="markets"),
            st.Page(chart_terminal_page, title="Trading Charts", icon=":material/show_chart:", url_path="charts"),
            st.Page(stock_research_page, title="Stock Research", icon=":material/article:", url_path="research"),
            st.Page(screener_page, title="Stock Screener", icon=":material/filter_alt:", url_path="screener"),
        ],
        "Strategy Lab": [
            st.Page(strategy_builder_page, title="Strategy Builder", icon=":material/rule:", url_path="builder"),
            st.Page(strategy_backtesting_page, title="Backtest Lab", icon=":material/query_stats:", url_path="backtests"),
            st.Page(backtest_comparison_page, title="Compare Runs", icon=":material/compare_arrows:", url_path="compare"),
        ],
        "Paper Practice": [
            st.Page(manual_paper_page, title="Manual Paper Trading", icon=":material/account_balance_wallet:", url_path="paper-manual"),
            st.Page(strategy_paper_page, title="Strategy Simulations", icon=":material/science:", url_path="paper-strategy"),
            st.Page(alert_center_page, title="Local Alerts", icon=":material/notifications_active:", url_path="alerts"),
        ],
        "System": [
            st.Page(data_management_page, title="Backup & Data", icon=":material/storage:", url_path="data"),
        ],
    }


def render_app() -> None:
    apply_theme()
    with st.sidebar:
        st.markdown("### QuantEdge")
        st.caption("Personal stock research and free strategy-testing terminal")
        st.divider()
        st.caption("**PAPER / HISTORICAL DATA ONLY**")
        st.caption("No broker connection or automated real-money execution.")
    router = st.navigation(navigation_pages(), position="sidebar", expanded=True)
    router.run()
