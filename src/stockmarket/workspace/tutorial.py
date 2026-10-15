"""In-app guide for free research and historical paper trading."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from .runtime import is_public_demo, workspace_path
from .ui import workspace_db
from .strategy_repository import StrategyRepository
from .strategy_schema import example_strategy


def synthetic_demo_bars() -> pd.DataFrame:
    """Reproducible FICTIONAL daily OHLCV, never market data."""
    time = pd.bdate_range("2025-05-01", periods=320, tz="UTC")
    t = np.arange(320, dtype=float)
    close = 100 + 0.09*t + 6*np.sin(t/11) + 9*np.sin(t/30)
    opening = np.r_[close[0], close[:-1]] + .35*np.sin(t/3)
    return pd.DataFrame({
        "open": opening, "close": close,
        "high": np.maximum(opening, close) + 1.2,
        "low": np.minimum(opening, close) - 1.2,
        "volume": np.rint(2000 + 400 * np.cos(t/8)),
    }, index=time)


def install_demo_example(db) -> dict:
    """Add a synthetic ticker and non-executable model strategy, offline."""
    symbol = "QEDMO"
    db.add_to_watchlist(db.default_watchlist(), symbol)
    bars = synthetic_demo_bars()
    db.save_candles(symbol, "1d", bars, provider="synthetic-tutorial")
    repo = StrategyRepository(db)
    name = "Tutorial: SMA and RSI on fictional data"
    if not any(row["name"] == name for row in repo.list_strategies()):
        config = example_strategy().model_copy(update={
            "name": name, "symbol": symbol,
            "description": "Demonstration only. Prices are fictional.",
        })
        repo.save(config)
    return {"symbol": symbol, "bars": len(bars)}


def tutorial_page() -> None:
    st.title("Start Here | Website Tutorial")
    st.caption("QuantEdge: free historical chart research, backtesting and paper-only practice.")
    if is_public_demo():
        st.warning("Public demo: every browser session gets its own temporary dataset. "
                   "Saved work can disappear after disconnection or server restart. "
                   "Do not upload private financial records.")
    else:
        st.info("Local mode: your practice history is saved in local SQLite. "
                "Use Backup & Data to export a copy.")

    use, publish, privacy = st.tabs(["Using QuantEdge", "Deploy your website", "Storage & safety"])
    with use:
        st.subheader("Try without signing up or paying")
        st.write("Load a fictional ticker (QEDMO) with 320 synthetic daily candles "
                 "and a sample SMA/RSI rule. This works completely offline.")
        if st.button("Load fictional demo stock and strategy", type="primary"):
            result = install_demo_example(workspace_db(workspace_path()))
            st.success(f"Loaded {result['bars']} fictional bars for {result['symbol']} "
                       "and a saved sample rule.")
        st.subheader("Step-by-step workflow")
        st.markdown(
            "1. **Market Explorer:** choose QEDMO, or add a real ticker (such as MSFT) "
            "and click Refresh to fetch historical candles.\n"
            "2. **Trading Charts:** select Daily, apply SMA/RSI/MACD overlays, "
            "zoom and inspect historical candles.\n"
            "3. **Strategy Builder:** load or create a strategy; choose entry/exit "
            "rules, risk limits, slippage and commission. Save it.\n"
            "4. **Backtest Lab:** select a saved strategy, period and simulated "
            "starting cash. Run, then review trade history, equity, drawdown, "
            "monthly returns and buy-and-hold.\n"
            "5. **Compare Runs:** save and compare runs. Check differing periods "
            "and assumptions before drawing conclusions.\n"
            "6. **Manual Paper Trading:** create an imaginary-cash account, "
            "then explicitly simulate BUY or SELL. No broker is involved.\n"
            "7. **Strategy Simulations:** create a separate, initially paused paper "
            "account; activate and process newly completed historical bars.\n"
            "8. **Local Alerts:** create historical-bar crossing alerts and "
            "review in-app events.\n"
            "9. **Backup & Data:** export results before leaving a temporary demo."
        )
        st.caption("QEDMO is NOT a listed stock. Fictional prices cannot demonstrate profitability.")
    with publish:
        st.subheader("Host on Streamlit Community Cloud")
        st.markdown(
            "1. Visit [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.\n"
            "2. Select Create app, then choose an existing app.\n"
            "3. Select repository **Shaurya-S0603/Quant-Edge-Terminal**, "
            "branch **main**, file **app.py**.\n"
            "4. Open Advanced settings, choose Python **3.12**, and place "
            "the following setting in Secrets.\n"
            "5. Pick an available subdomain and click Deploy.\n"
            "6. Visit the deployed address and test the fictional sample "
            "before sharing your website."
        )
        st.code('QUANTEDGE_PUBLIC_DEMO = "1"', language="toml")
        st.caption("The public-demo flag isolates each visitor's practice data. "
                   "For persistent personal results use local mode instead.")
        st.link_button("Official Streamlit deployment instructions",
                       "https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy")
    with privacy:
        st.markdown(
            "**Hosted public demo:** each visitor has a separate temporary "
            "SQLite database. Data can be lost on restart, session expiry or redeployment.\n\n"
            "**Local:** saved data stays on your computer and can be backed up.\n\n"
            "**Prices:** free data can be delayed or incomplete. QEDMO prices are synthetic.\n\n"
            "**Paper trades:** educational simulations only, not exchange execution.\n\n"
            "**Alerts:** in-app local events, not automatic push notifications."
        )
