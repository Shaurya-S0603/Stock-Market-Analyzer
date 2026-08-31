from __future__ import annotations

from streamlit.testing.v1 import AppTest


def test_navigation_accepts_callable_pages_with_explicit_routes() -> None:
    app = AppTest.from_string(
        '''
import streamlit as st

pages = {
    "Workspace": [
        st.Page(lambda: st.write("dashboard"), title="Dashboard", default=True),
        st.Page(lambda: st.write("markets"), title="Markets", url_path="markets"),
        st.Page(lambda: st.write("trader"), title="AI Trader", url_path="ai-trader"),
        st.Page(lambda: st.write("portfolio"), title="Portfolio", url_path="portfolio"),
        st.Page(lambda: st.write("journal"), title="Trade Journal", url_path="trade-journal"),
    ],
    "Research": [
        st.Page(lambda: st.write("models"), title="Model Analytics", url_path="model-analytics"),
        st.Page(lambda: st.write("backtest"), title="Backtesting", url_path="backtesting"),
        st.Page(lambda: st.write("risk"), title="Risk Analytics", url_path="risk-analytics"),
    ],
    "System": [
        st.Page(lambda: st.write("settings"), title="Settings", url_path="settings"),
    ],
}

navigation = st.navigation(pages, position="sidebar", expanded=True)
navigation.run()
'''
    ).run()

    assert not app.exception
