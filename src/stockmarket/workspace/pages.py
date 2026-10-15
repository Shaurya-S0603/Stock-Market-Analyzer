"""User-facing Phase 2 Charts, Stock Research, and cached Stock Screener pages."""
from __future__ import annotations

from .runtime import workspace_path

import os

import streamlit as st

from .charting import build_chart
from .database import clean_symbol
from .fundamentals import fetch_company_research
from .market_data import MarketDataError, MarketDataService
from .research_storage import INDICATORS, ResearchRepository
from .screener import screen_cached
from .ui import workspace_db


def _workspace():
    db = workspace_db(workspace_path())
    return db, ResearchRepository(db)


def _select_saved(repo: ResearchRepository, kind: str, key: str):
    items = repo.list(kind)
    choices = {"None": None}
    for item in items:
        choices[f"{item['name']} (#{item['id']})"] = item
    selected = st.selectbox("Saved " + ("layouts" if kind == "chart" else "screeners"),
                            list(choices), key=key)
    return choices[selected]


def chart_terminal_page() -> None:
    st.title("Interactive Chart Terminal")
    st.caption("OHLCV and indicators are computed only from accessible historical or cached bars. No live-price claims.")
    db, repo = _workspace()
    service = MarketDataService(db)
    selected = _select_saved(repo, "chart", "qe_saved_chart")
    if selected and st.button("Load saved chart"):
        config = selected["configuration"]
        for from_key, to_key in [
            ("symbol", "qe_ch_symbol"), ("interval", "qe_ch_interval"),
            ("chart_type", "qe_ch_type"), ("indicators", "qe_ch_indicators"),
            ("length", "qe_ch_length"), ("rsi_length", "qe_ch_rsi"),
            ("bollinger_std", "qe_ch_std"), ("volume", "qe_ch_volume")
        ]:
            st.session_state[to_key] = config[from_key]
        st.rerun()

    known = db.cached_symbols()
    if not known:
        st.info("No market history saved yet. Add a ticker in Market Explorer and press Refresh from provider.")
        return
    previous = st.session_state.get("qe_ch_symbol")
    if previous not in known:
        st.session_state["qe_ch_symbol"] = known[0]
    symbol = st.selectbox("Symbol", known, key="qe_ch_symbol")
    intervals = ["1d", "1h", "5m", "15m", "1wk", "1mo", "1m"]
    if st.session_state.get("qe_ch_interval") not in intervals:
        st.session_state["qe_ch_interval"] = "1d"
    col = st.columns(3)
    interval = col[0].selectbox("Timeframe", intervals, key="qe_ch_interval")
    chart_type = col[1].selectbox("Chart type", ["Candles", "OHLC", "Line", "Area"], key="qe_ch_type")
    available_periods = {
        "1m": ["5d", "7d"], "5m": ["5d", "30d", "60d"],
        "15m": ["5d", "30d", "60d"], "1h": ["5d", "30d", "60d"]
    }.get(interval, ["1mo", "3mo", "6mo", "1y", "2y", "5y"])
    period = col[2].selectbox("Provider history window", available_periods)
    indicator_choices = sorted(INDICATORS)
    if "qe_ch_indicators" not in st.session_state:
        st.session_state["qe_ch_indicators"] = ["SMA", "RSI"]
    enabled = st.multiselect("Technical indicators", indicator_choices, key="qe_ch_indicators")
    controls = st.columns(4)
    length = controls[0].slider("Rolling period", 2, 250, value=20, key="qe_ch_length")
    rsi_length = controls[1].slider("RSI / ATR / oscillator period", 2, 100, value=14, key="qe_ch_rsi")
    deviation = controls[2].slider("Bollinger standard deviations", .5, 4.0, 2.0, .25, key="qe_ch_std")
    volume = controls[3].checkbox("Volume panel", value=True, key="qe_ch_volume")
    config = {"symbol": symbol, "interval": interval, "chart_type": chart_type,
              "indicators": enabled, "length": length, "rsi_length": rsi_length,
              "bollinger_std": deviation, "volume": volume}

    from .strategy_repository import StrategyRepository
    from .manual_paper import ManualPaperRepository
    backtests = StrategyRepository(db)
    manuals = ManualPaperRepository(db)
    overlays = {"No simulated trade markers": None}
    for record in backtests.list_backtests():
        stored = backtests.load_backtest(record["id"])
        meta = stored["result"]["metadata"]
        if meta["symbol"] == symbol and meta["timeframe"] == interval:
            overlays[f"Backtest: {record['name']} (#{record['id']})"] = [
                {"timestamp": row["timestamp"], "side": row["side"], "price": row["price"]}
                for row in stored["result"].get("orders", []) if row.get("status") == "filled"
            ]
    if interval == "1d":
        for account in manuals.list_accounts():
            if account["symbol"] == symbol:
                overlays[f"Manual paper: {account['name']} (#{account['id']})"] = [
                    {"timestamp": row["observed_bar"], "side": row["side"], "price": row["price"]}
                    for row in manuals.list_orders(account["id"])
                ]
    overlay_name = st.selectbox("Show simulated entry/exit markers", list(overlays))
    refresh = st.button("Refresh selected symbol from free provider")
    try:
        result = service.history(symbol, interval=interval, period=period,
                                 refresh=refresh, offline=not refresh)
        if result.warning:
            st.warning(result.warning)
        st.caption(
            f"Source: {result.provider} · {result.origin} · {len(result.frame)} bars · "
            f"{result.frame.index[0]} through {result.frame.index[-1]} · "
            "UTC labels · unadjusted historical prices"
        )
        fig = build_chart(result.frame, config, markers=overlays[overlay_name])
        st.plotly_chart(fig, use_container_width=True, key="qe_financial_chart")
        with st.expander("Recent computed indicator values"):
            from .indicators import indicator_snapshot
            st.json(indicator_snapshot(result.frame, rsi_period=rsi_length, sma_period=length))
    except (MarketDataError, ValueError) as exc:
        st.info(str(exc))

    with st.expander("Save and manage chart layouts", expanded=False):
        layout_name = st.text_input("Layout name", value=(selected["name"] if selected else "My Chart"))
        actions = st.columns(3)
        if actions[0].button("Save new layout"):
            try:
                repo.save("chart", layout_name, config)
                st.success("Chart layout saved in local SQLite")
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
        if actions[1].button("Update selected", disabled=not selected):
            try:
                repo.save("chart", layout_name, config, item_id=selected["id"])
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
        if actions[2].button("Delete selected", disabled=not selected):
            repo.delete("chart", selected["id"])
            st.session_state.pop("qe_saved_chart", None)
            st.rerun()
        st.download_button("Export current chart layout JSON",
                           data=__import__("json").dumps(config, indent=2),
                           file_name="quantedge_chart_layout.json", mime="application/json")


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_research(symbol: str):
    return fetch_company_research(symbol)


def stock_research_page() -> None:
    st.title("Stock Research")
    st.caption("Provider-reported fundamentals and news are optional, may be delayed, and are never synthesized.")
    symbol = st.text_input("Company ticker", value="MSFT", key="qe_research_symbol")
    if st.button("Fetch or refresh accessible public research"):
        try:
            clean = clean_symbol(symbol)
            _cached_research.clear()
            with st.spinner("Requesting company fields from the public provider..."):
                st.session_state["qe_company_report"] = _cached_research(clean)
        except ValueError as exc:
            st.warning(str(exc))
    report = st.session_state.get("qe_company_report")
    if not report or report["symbol"] != symbol.strip().upper():
        st.info("Enter a ticker and request research. Network access is only used after you press Fetch.")
        return
    for warning in report["warnings"]:
        st.warning(warning)
    st.subheader("Company profile")
    if report["profile"]:
        st.dataframe([{"Field": k, "Reported value": v} for k, v in report["profile"].items()],
                     use_container_width=True, hide_index=True)
    else:
        st.info("No company profile fields supplied")
    st.subheader("Available fundamentals")
    if report["fundamentals"]:
        st.dataframe([{"Metric": k, "Reported value": v} for k, v in report["fundamentals"].items()],
                     use_container_width=True, hide_index=True)
    else:
        st.info("No supported fundamental fields supplied")
    st.subheader("Recent accessible news")
    if report["news"]:
        for article in report["news"]:
            st.write(f"**{article['Title']}** · {article['Source']} · {article['Published']}")
            st.link_button("Read original article", article["URL"])
    else:
        st.info("News is unavailable from the public provider for this symbol")


_SCREENER_FIELDS = {
    "min_price": ("Minimum saved close", 0.0, 10000000.0, 10.0),
    "max_price": ("Maximum saved close", 0.0, 10000000.0, 1000.0),
    "min_volume": ("Minimum saved daily volume", 0.0, 1000000000000.0, 100000.0),
    "min_change_pct": ("Minimum daily change (%)", -1000.0, 1000.0, 0.0),
    "max_change_pct": ("Maximum daily change (%)", -1000.0, 1000.0, 10.0),
    "rsi_min": ("Minimum RSI (14)", 0.0, 100.0, 40.0),
    "rsi_max": ("Maximum RSI (14)", 0.0, 100.0, 70.0),
    "above_sma": ("Close above SMA (period)", 2, 250, 20),
    "below_sma": ("Close below SMA (period)", 2, 250, 50),
}


def screener_page() -> None:
    st.title("Saved-Data Stock Screener")
    st.caption("Screens ONLY locally downloaded 1-day price data. Not a real-time or whole-market screener.")
    db, repo = _workspace()
    saved = _select_saved(repo, "screener", "qe_saved_screener")
    if saved and st.button("Load saved screener"):
        filters = saved["configuration"]["filters"]
        for key, (_, _, _, default) in _SCREENER_FIELDS.items():
            st.session_state["qe_scan_on_"+key] = key in filters
            st.session_state["qe_scan_"+key] = filters.get(key, default)
        st.rerun()
    lists = db.list_watchlists()
    choices = ["All saved symbols"] + [str(item["name"]) for item in lists]
    universe_option = st.selectbox("Symbol universe", choices)
    if universe_option == "All saved symbols":
        universe = db.cached_symbols()
    else:
        active = next(item for item in lists if item["name"] == universe_option)
        universe = db.symbols_in_watchlist(active["id"])
    st.caption(f"{len(universe)} symbols in selected universe; those without saved daily candles are omitted.")
    with st.form("qe_screener_form"):
        criteria = {}
        cols = st.columns(3)
        for i, (key, (label, minimum, maximum, default)) in enumerate(_SCREENER_FIELDS.items()):
            with cols[i % 3]:
                enabled = st.checkbox("Use " + label, value=False, key="qe_scan_on_"+key)
                value = st.number_input(label, min_value=minimum, max_value=maximum, value=default,
                                        step=1 if key in {"above_sma", "below_sma"} else 1.0,
                                        key="qe_scan_"+key)
                if enabled:
                    criteria[key] = int(value) if key in {"above_sma", "below_sma"} else float(value)
        run = st.form_submit_button("Run cached screener")
    config = {"version": 1, "filters": criteria}
    if run:
        try:
            st.session_state["qe_scan_results"] = screen_cached(db, universe, config)
        except ValueError as exc:
            st.warning(str(exc))
    results = st.session_state.get("qe_scan_results")
    if results is not None:
        st.subheader("Matching cached securities")
        if results.empty:
            st.info("No symbols matched, or usable daily history is missing.")
        else:
            st.dataframe(results, hide_index=True, use_container_width=True)
            st.download_button("Export results as CSV", results.to_csv(index=False),
                               file_name="quantedge_screener.csv", mime="text/csv")
    with st.expander("Manage saved screening filters"):
        label = st.text_input("Screener name", value=(saved["name"] if saved else "My Screener"))
        cols = st.columns(3)
        if cols[0].button("Save new screener"):
            try:
                repo.save("screener", label, config)
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
        if cols[1].button("Update selected", disabled=not saved):
            try:
                repo.save("screener", label, config, item_id=saved["id"])
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
        if cols[2].button("Delete selected", disabled=not saved):
            repo.delete("screener", saved["id"])
            st.session_state.pop("qe_saved_screener", None)
            st.rerun()
