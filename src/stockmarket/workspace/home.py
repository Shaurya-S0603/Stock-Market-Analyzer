"""Focused personal market terminal, not a generic ML/trader dashboard."""
from __future__ import annotations

from .runtime import workspace_path

import os
import pandas as pd
import streamlit as st

from .ui import workspace_db
from .strategy_repository import StrategyRepository
from .strategy_paper import PaperStrategyRepository
from .manual_paper import ManualPaperRepository
from .alerts import AlertRepository


def personal_dashboard_page() -> None:
    st.title("QuantEdge | Personal Market Workspace")
    st.caption("Your private TradingView-style research and strategy test bench. "
               "Quotes are historical/cached, not guaranteed live. All trading is simulated.")
    db = workspace_db(workspace_path())
    symbols = db.cached_symbols()
    lists = db.list_watchlists()
    saved = StrategyRepository(db).list_strategies()
    paper = PaperStrategyRepository(db).list_accounts()
    manual = ManualPaperRepository(db).list_accounts()
    events = AlertRepository(db).list_events(limit=8)
    cols = st.columns(4)
    cols[0].metric("Tracked symbols", len(symbols))
    cols[1].metric("Watchlists", len(lists))
    cols[2].metric("Saved strategies", len(saved))
    cols[3].metric("Paper portfolios", len(paper) + len(manual))

    st.subheader("Market watch")
    if not symbols:
        st.info("Add a ticker in **Market Explorer** and download its historical data to start.")
    else:
        table = []
        for symbol in symbols:
            data = db.load_candles(symbol, "1d")
            if len(data) >= 2:
                # Penultimate entry is safer for manual paper execution and data provenance.
                row = data.iloc[-2]
                earlier = data.iloc[-3] if len(data) >= 3 else None
                change = (float(row["close"]) / float(earlier["close"]) - 1) * 100 if earlier is not None else None
                table.append({"Ticker":symbol, "Saved completed close":round(float(row["close"]), 4),
                              "Change %":round(change, 3) if change is not None else None,
                              "Completed bar":str(data.index[-2]), "Provider":row["provider"],
                              "Price basis":row["adjustment_mode"]})
            else:
                table.append({"Ticker":symbol, "Saved completed close":None,
                              "Change %":None, "Completed bar":None,
                              "Provider":"Not cached", "Price basis":None})
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
        st.caption("Latest candle excluded because it might still be forming. "
                   "No claim of exchange-open or real-time quote status.")

    left, right = st.columns(2)
    with left:
        st.subheader("Paper-testing snapshot")
        summaries = []
        manual_repo = ManualPaperRepository(db)
        strategy_repo = PaperStrategyRepository(db)
        for account in manual:
            try:
                state = manual_repo.summary(account["id"])
                summaries.append({"Portfolio":account["name"], "Mode":"Manual",
                                  "Symbol":account["symbol"], "Paper equity":round(state["equity"],2),
                                  "Return %":round(state["total_return_pct"],2)})
            except ValueError:
                continue
        for account in paper:
            state = strategy_repo.summary(account["id"])
            summaries.append({"Portfolio":account["label"], "Mode":"Strategy",
                              "Symbol":account["symbol"], "Paper equity":round(state["equity"],2),
                              "Return %":round(state["return_pct"],2)})
        if summaries:
            st.dataframe(summaries, hide_index=True, use_container_width=True)
        else:
            st.info("No paper accounts yet. Start with **Manual Paper Trading** or **Strategy Simulations**.")
    with right:
        st.subheader("Recent alert activity")
        if events:
            st.dataframe(pd.DataFrame(events)[["bar_time", "observed_close", "description"]],
                         hide_index=True, use_container_width=True)
        else:
            st.info("No triggered local alerts. Configure one under **Alerts**.")
    st.subheader("Suggested research flow")
    st.markdown("**1. Market Explorer** → **2. Charts** → **3. Strategy Builder** → "
                "**4. Backtest Lab** → **5. Compare Runs** → **6. Paper Trading** → **7. Alerts**")
    st.caption("Free local data and research. Backtests are hypothetical and do not predict future profits.")
