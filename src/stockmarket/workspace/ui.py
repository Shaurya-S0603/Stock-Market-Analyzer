"""Standalone Streamlit market-explorer surface using persistent workspace services."""
from __future__ import annotations

import os

import plotly.graph_objects as go
import streamlit as st

from .database import WorkspaceDB, clean_symbol
from .market_data import MarketDataError, MarketDataService, YahooMarketAdapter


@st.cache_resource
def workspace_db(db_path: str) -> WorkspaceDB:
    return WorkspaceDB(db_path)


def _chart(frame, symbol: str, chart_type: str):
    figure = go.Figure()
    x = frame.index
    if chart_type == "Candles":
        figure.add_trace(go.Candlestick(
            x=x, open=frame["open"], high=frame["high"], low=frame["low"],
            close=frame["close"], name=symbol,
        ))
    else:
        figure.add_trace(go.Scatter(x=x, y=frame["close"], name=symbol, mode="lines"))
    figure.update_layout(
        height=440, margin=dict(l=8, r=8, t=25, b=10),
        template="plotly_dark", xaxis_rangeslider_visible=False,
        title=symbol + " · saved historical OHLCV",
        xaxis_title="UTC (daily dates are session labels)",
        yaxis_title="Price (provider currency)",
    )
    return figure


def market_explorer_page() -> None:
    st.title("Market Explorer & Watchlists")
    st.caption("Free-data research terminal. No brokerage access; price charts are historical or cached, never promised real-time.")
    try:
        db = workspace_db(os.getenv("QUANTEDGE_WORKSPACE_DB", ".data/workspace.db"))
        service = MarketDataService(db)
        db.default_watchlist()
    except Exception as exc:
        st.error("Unable to initialize the local workspace database: " + str(exc))
        return

    lists = db.list_watchlists()
    selected_name = st.selectbox("Active watchlist", [item["name"] for item in lists], key="workspace_list_name")
    active = next(item for item in lists if item["name"] == selected_name)
    list_id = int(active["id"])
    symbols = db.symbols_in_watchlist(list_id)

    with st.expander("Manage watchlists", expanded=False):
        add_col, rename_col, delete_col = st.columns(3)
        with add_col:
            with st.form("workspace_create_list"):
                name = st.text_input("New watchlist name")
                if st.form_submit_button("Create watchlist"):
                    try:
                        db.create_watchlist(name)
                        st.rerun()
                    except ValueError as exc:
                        st.warning(str(exc))
        with rename_col:
            with st.form("workspace_rename_list"):
                name = st.text_input("Rename active watchlist", value=selected_name)
                if st.form_submit_button("Rename"):
                    try:
                        db.rename_watchlist(list_id, name)
                        st.session_state.pop("workspace_list_name", None)
                        st.rerun()
                    except ValueError as exc:
                        st.warning(str(exc))
        with delete_col:
            st.caption("Deleting a list does not delete market history or another list.")
            if st.button("Delete active watchlist"):
                db.delete_watchlist(list_id)
                db.default_watchlist()
                st.session_state.pop("workspace_list_name", None)
                st.rerun()

    with st.form("workspace_add_symbol"):
        col_a, col_b = st.columns([3, 1])
        requested = col_a.text_input("Add market ticker (e.g. MSFT, AAPL, D05.SI)")
        submitted = col_b.form_submit_button("Add to watchlist", use_container_width=True)
        if submitted:
            try:
                db.add_to_watchlist(list_id, requested)
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))

    with st.expander("Search by ticker or company name"):
        query = st.text_input("Search accessible Yahoo symbols")
        if st.button("Search Yahoo", disabled=not query.strip()):
            try:
                results = YahooMarketAdapter().search(query)
                if results:
                    st.dataframe(results, hide_index=True, use_container_width=True)
                else:
                    st.info("No matches returned. Exact tickers may still be entered above.")
            except MarketDataError as exc:
                st.warning(str(exc))

    if not symbols:
        st.info("This watchlist is empty. Add a ticker above to inspect its saved or available historical candles.")
        return

    st.subheader("Saved watchlist")
    overview = []
    for symbol in symbols:
        daily = db.load_candles(symbol, "1d")
        if daily.empty:
            overview.append({"Symbol": symbol, "Last historical close": None, "UTC timestamp": None, "Source": "not downloaded"})
        else:
            last = daily.iloc[-1]
            overview.append({
                "Symbol": symbol, "Last historical close": float(last["close"]),
                "UTC timestamp": str(daily.index[-1]), "Source": "saved historical cache",
            })
    st.dataframe(overview, hide_index=True, use_container_width=True)

    col1, col2, col3 = st.columns([2, 1, 1])
    symbol = col1.selectbox("Inspect symbol", symbols, key="workspace_active_symbol")
    interval = col2.selectbox("Timeframe", ["1d", "1h", "5m", "15m", "1wk", "1mo", "1m"], index=0)
    period_choices = {
        "1m": ["5d", "7d"], "5m": ["5d", "30d", "60d"],
        "15m": ["5d", "30d", "60d"], "1h": ["5d", "30d", "60d"],
    }
    choices = period_choices.get(interval, ["1mo", "3mo", "6mo", "1y", "2y", "5y"])
    period = col3.selectbox("History requested", choices, index=min(2, len(choices)-1))
    if interval in ("1m", "5m", "15m", "1h"):
        st.caption("Intraday history is limited by the free provider; longer periods are available as daily/weekly bars.")
    actions = st.columns(3)
    refresh = actions[0].button("Refresh from provider", use_container_width=True)
    offline = actions[1].checkbox("Offline/cached only", value=False)
    chart_type = actions[2].radio("Chart", ["Candles", "Line"], horizontal=True)

    try:
        # No background downloads just because Streamlit reran; explicit Refresh is deliberate.
        result = service.history(symbol, period=period, interval=interval, refresh=refresh, offline=not refresh)
    except MarketDataError as exc:
        st.info(str(exc))
        result = None

    if result is not None:
        frame = result.frame
        if result.warning:
            st.warning(result.warning)
        st.caption(
            f"Source: {result.provider} · {result.origin} · {len(frame)} bars · "
            f"{frame.index[0]} to {frame.index[-1]} · UTC labels · "
            "raw/unadjusted data by default"
        )
        st.plotly_chart(_chart(frame, symbol, chart_type), use_container_width=True)
        st.download_button(
            "Export saved bars as CSV",
            data=frame.to_csv().encode("utf-8"),
            file_name=f"{symbol.replace('.', '_')}_{interval}_history.csv",
            mime="text/csv",
        )
    if st.button("Remove selected symbol from watchlist"):
        db.remove_from_watchlist(list_id, symbol)
        st.session_state.pop("workspace_active_symbol", None)
        st.rerun()
