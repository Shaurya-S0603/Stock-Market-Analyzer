from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class UISettings:
    watchlist: list[str]
    period: str
    interval: str
    horizon: int
    buy_threshold: float
    sell_threshold: float
    starting_cash: float
    commission_rate: float
    slippage_rate: float
    automation_enabled: bool
    stop_loss_pct: float
    take_profit_pct: float


def sanitize_symbol(symbol: str) -> str:
    cleaned = "".join(ch for ch in symbol.upper().strip() if ch.isalnum() or ch in {".", "-"})
    if cleaned == "APPL":
        return "AAPL"
    return cleaned or "MSFT"


def parse_watchlist(raw_watchlist: str) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for chunk in raw_watchlist.split(","):
        symbol = sanitize_symbol(chunk)
        if symbol not in seen:
            unique.append(symbol)
            seen.add(symbol)
    return unique or ["MSFT"]


def effective_period(period: str, interval: str) -> str:
    if interval in {"5m", "15m", "30m"} and period not in {"5d", "10d", "30d", "60d"}:
        return "60d"
    return period


def render_sidebar() -> UISettings:
    with st.sidebar:
        st.header("Controls")
        raw_watchlist = st.text_input("Watchlist symbols", value="MSFT, AAPL, GOOGL", help="Enter comma-separated Yahoo Finance ticker symbols.")
        period = st.selectbox("History window", ["5d", "10d", "30d", "60d", "3mo", "6mo"], index=3)
        interval = st.selectbox("Bar interval", ["5m", "15m", "30m", "1h"], index=0)
        horizon = st.slider("Forecast horizon (bars)", 1, 48, 12, help="Number of bars ahead represented by the target return.")
        st.subheader("Signal settings")
        buy_threshold = st.slider("Buy threshold (%)", 0.1, 10.0, 0.5, 0.1) / 100.0
        sell_threshold = -(st.slider("Sell threshold (%)", 0.1, 10.0, 0.5, 0.1) / 100.0)
        st.subheader("Paper portfolio")
        starting_cash = st.number_input("Starting cash", min_value=1_000.0, value=100_000.0, step=1_000.0)
        commission_rate = st.number_input("Commission rate", min_value=0.0, max_value=0.05, value=0.001, step=0.0005, format="%.4f")
        slippage_rate = st.number_input("Slippage rate", min_value=0.0, max_value=0.05, value=0.0005, step=0.0005, format="%.4f")
        st.subheader("Risk automation")
        automation_enabled = st.toggle("Enable stop-loss / take-profit", value=False)
        stop_loss_pct = st.slider("Stop-loss (%)", 0.5, 20.0, 2.0, 0.5)
        take_profit_pct = st.slider("Take-profit (%)", 0.5, 30.0, 4.0, 0.5)
        st.caption("Changing portfolio cash or cost assumptions resets the in-memory paper account.")
    return UISettings(parse_watchlist(raw_watchlist), effective_period(period, interval), interval, horizon, buy_threshold, sell_threshold, float(starting_cash), float(commission_rate), float(slippage_rate), automation_enabled, float(stop_loss_pct), float(take_profit_pct))
