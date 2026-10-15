"""Local notification center and isolated opt-in strategy simulation controls."""
from __future__ import annotations

from .runtime import workspace_path

import os

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from .alerts import AlertRepository
from .market_data import VALID_INTERVALS
from .strategy_paper import PaperStrategyRepository
from .strategy_repository import StrategyRepository
from .ui import workspace_db


def _services():
    db = workspace_db(workspace_path())
    return db, StrategyRepository(db), AlertRepository(db), PaperStrategyRepository(db)


def alert_center_page() -> None:
    st.title("Local Alerts")
    st.caption("Completed historical-bar signals only. Alerts are stored locally, not pushed to your phone or sent by email. No brokerage actions.")
    db, strategies, alerts, _ = _services()
    symbols = db.cached_symbols()
    if not symbols:
        st.info("Download historical candles in Market Explorer before setting up alerts.")
        return
    kinds = ["price_cross", "rsi_cross", "sma_cross", "strategy_entry", "strategy_exit"]
    strategies_available = strategies.list_strategies()
    with st.form("local_alert_create"):
        cols = st.columns(3)
        label = cols[0].text_input("Alert name",value="Research alert")
        kind = cols[1].selectbox("Condition",kinds)
        symbol = cols[2].selectbox("Symbol",symbols)
        interval = st.selectbox("Bar timeframe",["1d","1h","5m","15m","1wk","1mo","1m"])
        opts = st.columns(3)
        direction = opts[0].selectbox("Crossing direction",["above","below"])
        threshold = opts[1].number_input("Price / RSI threshold",min_value=0.,max_value=1e9,value=60.)
        period = opts[2].number_input("Indicator lookback",min_value=2,max_value=250,value=14,step=1)
        selection = st.selectbox("Pinned strategy (only for strategy alerts)",
                                ["None"]+[f"{s['name']} (#{s['id']}, v{s['latest_version']})" for s in strategies_available])
        submitted = st.form_submit_button("Create disabled-history-safe alert")
    if submitted:
        try:
            parsed = {"symbol":symbol,"interval":interval,"kind":kind,
                      "direction":direction,"threshold":float(threshold),"period":int(period)}
            if kind.startswith("strategy_"):
                if selection == "None":
                    raise ValueError("Choose a pinned strategy for a strategy signal alert")
                strat = next(s for s in strategies_available if
                             selection==f"{s['name']} (#{s['id']}, v{s['latest_version']})")
                parsed["strategy_id"]=strat["id"]
                parsed["strategy_version"]=strat["latest_version"]
            number=alerts.add(label,parsed)
            st.success(f"Saved alert #{number}. Prior historical crossings will not notify.")
            st.rerun()
        except (ValueError,ValidationError) as exc:
            st.error(str(exc))
    if st.button("Evaluate new completed cached bars", key="qe_alert_poll"):
        try:
            outcome = alerts.evaluate()
            st.success(f"{outcome['new_events']} new alert(s), {outcome['bars_examined']} bars evaluated.")
        except ValueError as exc:
            st.error(str(exc))
    rows=alerts.list_rules()
    st.subheader("Alert rules")
    if not rows:
        st.info("No alerts configured")
    for alert in rows:
        left,right=st.columns([4,2])
        left.write(f"**#{alert['id']} {alert['label']}** · {alert['definition']['symbol']} / {alert['definition']['interval']} · {alert['definition']['kind']} · {'ENABLED' if alert['enabled'] else 'PAUSED'}")
        with right:
            c=st.columns(2)
            if c[0].button("Pause" if alert["enabled"] else "Enable",key=f"qe_alert_toggle_{alert['id']}"):
                try:
                    alerts.set_enabled(alert["id"],not alert["enabled"])
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            if c[1].button("Delete",key=f"qe_alert_delete_{alert['id']}"):
                alerts.delete(alert["id"])
                st.rerun()
    st.subheader("Local alert history")
    events=alerts.list_events()
    if events:
        st.dataframe(pd.DataFrame(events),use_container_width=True,hide_index=True)
    else:
        st.info("No new confirmed-bar crossings yet.")


def strategy_paper_page() -> None:
    st.title("Isolated Strategy Simulations")
    st.caption("Long-only, paper-only simulations; separate from your manual portfolio and legacy AI Trader. All new simulations begin paused.")
    db, strategy_repo, _, paper = _services()
    saved=strategy_repo.list_strategies()
    if saved:
        with st.form("qe_new_simulation"):
            choice=st.selectbox("Saved strategy version to freeze",[
                f"{s['name']} (#{s['id']}, v{s['latest_version']})" for s in saved])
            label=st.text_input("Simulation name",value="My strategy experiment")
            starting=st.number_input("Starting simulated cash",min_value=1.,max_value=1e9,
                                      value=10000.,step=500.)
            create=st.form_submit_button("Create paused simulation")
        if create:
            picked=next(s for s in saved if choice==f"{s['name']} (#{s['id']}, v{s['latest_version']})")
            try:
                number=paper.create(picked["id"],starting_cash=float(starting),label=label)
                st.success(f"Created independent simulated account #{number}, initially paused.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    else:
        st.info("Save a rule-based strategy in Strategy Builder to create a simulation.")
    accounts=paper.list_accounts()
    if not accounts:
        return
    options={f"#{a['id']} {a['label']} · {'ACTIVE' if a['enabled'] else 'PAUSED'}":a for a in accounts}
    selected=st.selectbox("Choose simulated account",list(options))
    acct=options[selected]
    summary=paper.summary(acct["id"])
    cols=st.columns(4)
    cols[0].metric("Simulated equity",f"{summary['equity']:,.2f}")
    cols[1].metric("Cash",f"{summary['cash']:,.2f}")
    cols[2].metric("Shares",str(summary["shares"]))
    cols[3].metric("Paper return",f"{summary['return_pct']:+.2f}%")
    st.caption(f"Last processed confirmed bar: {summary['last_processed']} · {summary['symbol']} / {summary['interval']} · {summary['provider']} · strategy version {summary['strategy_version']}")
    with st.expander("Simulation state and P&L"):
        st.json(summary)
    actions=st.columns(2)
    if actions[0].button("Pause" if acct["enabled"] else "Enable paper simulation"):
        try:
            paper.set_enabled(acct["id"],not acct["enabled"])
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if actions[1].button("Process new completed cached bars",disabled=not acct["enabled"]):
        try:
            result=paper.cycle(acct["id"])
            st.success(f"{result['bars']} completed new bar(s), {result['fills']} simulated fill(s).")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    st.subheader("Paper fill journal")
    fills=paper.list_fills(acct["id"])
    if fills:
        st.dataframe(pd.DataFrame(fills),use_container_width=True,hide_index=True)
    else:
        st.info("No fills yet. A strategy waits for newly completed bars after activation.")
    with st.expander("Decision audit"):
        decisions=paper.list_decisions(acct["id"])
        if decisions:
            st.dataframe(pd.DataFrame(decisions),use_container_width=True,hide_index=True)
        else:
            st.info("No observations processed yet.")
