"""Streamlit manual paper orders at completed cached closes, never real quotes."""
from __future__ import annotations

from .runtime import workspace_path
import os
import pandas as pd
import streamlit as st

from .manual_paper import ManualPaperRepository
from .ui import workspace_db


def manual_paper_page() -> None:
    st.title("Manual Paper Trading")
    st.caption("Practice simulated BUY/SELL decisions without depositing money or connecting a broker. "
               "Execution uses the last completed saved DAILY close, not a real-time market order.")
    db = workspace_db(workspace_path())
    repo = ManualPaperRepository(db)
    symbols = [s for s in db.cached_symbols() if len(db.load_candles(s,"1d")) >= 3]
    if symbols:
        with st.expander("Create a paper portfolio", expanded=not bool(repo.list_accounts())):
            with st.form("qe_manual_create"):
                name = st.text_input("Portfolio name", value="Practice portfolio")
                ticker = st.selectbox("Single symbol (shared price/currency basis)", symbols)
                cash = st.number_input("Starting imaginary capital", min_value=1.,max_value=1e9,
                                       value=10000., step=1000.)
                created = st.form_submit_button("Create paper account")
            if created:
                try:
                    number = repo.create(name,ticker,float(cash))
                    st.success(f"Created paper portfolio #{number}")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    else:
        st.info("Download at least 3 daily candles for a ticker in **Market Explorer** before creating a portfolio.")
    options = {f"#{a['id']} {a['name']} ({a['symbol']})": a for a in repo.list_accounts()}
    if not options:
        return
    chosen = st.selectbox("Select practice portfolio",list(options))
    account = options[chosen]
    try:
        state=repo.summary(account["id"])
    except ValueError as exc:
        st.error(str(exc))
        return
    cols=st.columns(4)
    cols[0].metric("Simulated equity",f"{state['equity']:,.2f}")
    cols[1].metric("Simulated cash",f"{state['cash']:,.2f}")
    cols[2].metric("Shares held",state["shares"])
    cols[3].metric("Simulated return",f"{state['total_return_pct']:+.2f}%")
    st.caption(f"Price source: {state['price_provider']} · last completed candle: {state['last_completed_bar']} · "
               f"saved price: {state['last_completed_close']:,.4f}. "
               "Trades are recorded now but filled at that *historical* candle close plus modeled costs.")
    with st.form("qe_manual_order"):
        st.subheader("Simulate an order")
        controls=st.columns(2)
        side=controls[0].selectbox("Action",["buy","sell"],format_func=lambda x:x.upper())
        quantity=int(controls[1].number_input("Whole shares", min_value=1,max_value=1_000_000,value=1,step=1))
        costs=st.columns(3)
        fixed=costs[0].number_input("Flat fee",min_value=0.,max_value=1000.,value=0.)
        pct=costs[1].number_input("Commission (%)",min_value=0.,max_value=10.,value=0.)
        slip=costs[2].number_input("Slippage (%)",min_value=0.,max_value=10.,value=0.05)
        acknowledged=st.checkbox("I understand this is a simulated historical-price fill, not a market quote.")
        submitted=st.form_submit_button("Place simulated order",disabled=not acknowledged)
    if submitted:
        try:
            receipt=repo.order(account["id"],side,quantity,commission_fixed=float(fixed),
                               commission_pct=float(pct),slippage_pct=float(slip))
            st.success(f"PAPER {receipt['side'].upper()} {receipt['quantity']} "
                       f"@ {receipt['price']:.4f}, fee {receipt['fee']:.4f}. Saved in local journal.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    st.subheader("Simulated trade journal")
    records=repo.list_orders(account["id"])
    if records:
        trades=pd.DataFrame(records)
        st.dataframe(trades,hide_index=True,use_container_width=True)
        st.download_button("Export paper orders CSV",trades.to_csv(index=False),
                           file_name="quantedge_manual_paper_orders.csv",mime="text/csv")
    else:
        st.info("No simulated orders in this account yet.")
    with st.expander("Portfolio details and P&L"):
        st.json({key:value for key,value in state.items()
                 if key not in {"created_at"}})
