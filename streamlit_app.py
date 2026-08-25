from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent / "src"))

from stockmarket.backtest import run_backtest
from stockmarket.data import MarketDataError, YahooFinanceProvider
from stockmarket.features import build_features
from stockmarket.modeling import train_model, walk_forward_scores
from stockmarket.signals import make_signal
from stockmarket.storage import Store
from stockmarket.trading import PaperPortfolio, TradingError


st.set_page_config(page_title="Paper Market Lab", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
        --ink: #d8ffe4;
        --muted: #8ec5a1;
        --panel: #07130d;
        --panel-2: #0d1f16;
        --brand: #22c55e;
        --accent: #14b8a6;
        --line: #1f3d2d;
    }

    html, body, [class*="css"] {
        font-family: 'Space Grotesk', sans-serif;
        color: var(--ink);
    }

    [data-testid="stAppViewContainer"] {
        background: radial-gradient(1000px 500px at 100% -10%, rgba(20, 184, 166, 0.15) 0%, transparent 62%),
                    linear-gradient(180deg, #020905 0%, #05110b 100%);
    }

    .hero {
        background: linear-gradient(135deg, #0b2a1a 0%, #0f5132 100%);
        border-radius: 18px;
        padding: 24px 26px;
        color: #eafff1;
        border: 1px solid rgba(34, 197, 94, 0.45);
        box-shadow: 0 16px 34px rgba(0, 0, 0, 0.45);
        margin-bottom: 14px;
    }

    .hero h1 {
        margin: 0;
        font-size: 2rem;
        letter-spacing: 0.2px;
        color: #ecfff2;
    }

    .hero p {
        margin-top: 8px;
        margin-bottom: 0;
        color: #b8f2cb;
        font-size: 1rem;
    }

    .status-chip {
        display: inline-block;
        margin-top: 12px;
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        letter-spacing: 0.35px;
        text-transform: uppercase;
        background: rgba(0, 0, 0, 0.25);
        border: 1px solid rgba(34, 197, 94, 0.55);
        color: #ceffd9;
    }

    .section-title {
        font-size: 1.08rem;
        font-weight: 700;
        margin-top: 10px;
        margin-bottom: 2px;
        color: #ccf6d7;
    }

    div[data-testid="stMetric"] {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 14px;
    }

    div[data-testid="stMetric"] label {
        color: #8bc79f;
    }

    .mono {
        font-family: 'IBM Plex Mono', monospace;
        color: #7fb891;
        font-size: 0.85rem;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #04150d 0%, #061d12 100%);
        border-right: 1px solid #1a3d2b;
    }

    div[data-testid="stDataFrame"], div[data-testid="stTable"] {
        border: 1px solid #1f3d2d;
        border-radius: 12px;
        overflow: hidden;
    }

    [data-testid="stTabs"] button {
        color: #b6efc8;
        border-radius: 10px 10px 0 0;
    }

    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #e8ffee;
        background: #0b2318;
    }

    div.stButton > button {
        background: linear-gradient(120deg, #15803d, #22c55e 55%, #14b8a6);
        color: #00190b;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        padding: 0.58rem 0.95rem;
    }

    div.stDownloadButton > button {
        background: #0d2f1e;
        color: #b8f9cc;
        border: 1px solid #2bb060;
        border-radius: 10px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=120)
def load_market_data(symbol: str, period: str, interval: str) -> pd.DataFrame:
    return YahooFinanceProvider().fetch(symbol, period, interval)


def sanitize_symbol(symbol: str) -> str:
    cleaned = "".join(ch for ch in symbol.upper().strip() if ch.isalnum() or ch in {".", "-"})
    if cleaned == "APPL":
        return "AAPL"
    return cleaned or "MSFT"


def parse_watchlist(raw_watchlist: str) -> list[str]:
    symbols = [sanitize_symbol(chunk) for chunk in raw_watchlist.split(",")]
    unique = []
    seen = set()
    for symbol in symbols:
        if symbol and symbol not in seen:
            unique.append(symbol)
            seen.add(symbol)
    return unique or ["MSFT"]


def effective_period(period: str, interval: str) -> str:
    intraday_allowed = {"5d", "10d", "30d", "60d"}
    if interval in {"5m", "15m", "30m"} and period not in intraday_allowed:
        return "60d"
    return period


def format_orders_table(order_rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(order_rows)
    if frame.empty:
        return frame
    if "realized_pnl" not in frame.columns:
        frame["realized_pnl"] = 0.0
    if "reason" not in frame.columns:
        frame["reason"] = "manual"
    frame = frame.rename(
        columns={
            "symbol": "Symbol",
            "side": "Side",
            "quantity": "Qty",
            "price": "Fill Price",
            "fee": "Fee",
            "realized_pnl": "Realized PnL",
            "reason": "Reason",
            "created_at": "Time",
        }
    )
    return frame[["Time", "Symbol", "Side", "Qty", "Fill Price", "Fee", "Realized PnL", "Reason"]]


def render_candles_with_volume(bars: pd.DataFrame, symbol: str) -> None:
    if bars.empty:
        st.info("No bars available for charting.")
        return
    chart_frame = bars.tail(260).reset_index().rename(columns={"index": "timestamp"})
    if "Datetime" in chart_frame.columns:
        chart_frame = chart_frame.rename(columns={"Datetime": "timestamp"})
    if "Date" in chart_frame.columns:
        chart_frame = chart_frame.rename(columns={"Date": "timestamp"})
    if "timestamp" not in chart_frame.columns:
        chart_frame["timestamp"] = bars.tail(260).index
    chart_frame["timestamp"] = pd.to_datetime(chart_frame["timestamp"], errors="coerce")
    chart_frame = chart_frame.dropna(subset=["timestamp"]).sort_values("timestamp")
    if chart_frame.empty:
        st.info("Chart data is unavailable after timestamp normalization.")
        return
    chart_frame["ema_20"] = chart_frame["Close"].ewm(span=20, adjust=False).mean()

    increasing = chart_frame["Close"] >= chart_frame["Open"]
    volume_colors = ["#22c55e" if is_up else "#f43f5e" for is_up in increasing]

    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28],
    )
    figure.add_trace(
        go.Candlestick(
            x=chart_frame["timestamp"],
            open=chart_frame["Open"],
            high=chart_frame["High"],
            low=chart_frame["Low"],
            close=chart_frame["Close"],
            increasing_line_color="#22c55e",
            decreasing_line_color="#f43f5e",
            increasing_fillcolor="#22c55e",
            decreasing_fillcolor="#f43f5e",
            name="Price",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=chart_frame["timestamp"],
            y=chart_frame["ema_20"],
            mode="lines",
            line={"color": "#14b8a6", "width": 2},
            name="EMA 20",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Bar(
            x=chart_frame["timestamp"],
            y=chart_frame["Volume"],
            marker={"color": volume_colors},
            name="Volume",
            opacity=0.85,
        ),
        row=2,
        col=1,
    )
    figure.update_layout(
        title=f"{symbol} Candlestick + Volume",
        height=560,
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        paper_bgcolor="#07130d",
        plot_bgcolor="#07130d",
        font={"color": "#d8ffe4", "family": "Space Grotesk"},
        xaxis_rangeslider_visible=False,
        legend={"orientation": "h", "y": 1.02, "x": 0.02},
    )
    figure.update_xaxes(showgrid=True, gridcolor="#123322", zeroline=False)
    figure.update_yaxes(showgrid=True, gridcolor="#123322", zeroline=False)
    st.plotly_chart(figure, width="stretch")


def position_table(portfolio: PaperPortfolio, prices: dict[str, float]) -> pd.DataFrame:
    rows = portfolio.positions_snapshot(prices)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.rename(
        columns={
            "symbol": "Symbol",
            "quantity": "Qty",
            "avg_cost": "Avg Cost",
            "market_price": "Mark",
            "market_value": "Market Value",
            "cost_basis": "Cost Basis",
            "unrealized_pnl": "Unrealized PnL",
            "unrealized_pct": "Unrealized %",
            "realized_pnl": "Realized PnL",
        }
    )
    return frame


def apply_risk_automation(
    portfolio: PaperPortfolio,
    store: Store,
    latest_prices: dict[str, float],
    stop_loss_pct: float,
    take_profit_pct: float,
    automation_enabled: bool,
) -> list[str]:
    events = []
    if not automation_enabled:
        return events
    for symbol, position in list(portfolio.positions.items()):
        if position.quantity <= 0:
            continue
        mark = latest_prices.get(symbol)
        if mark is None or position.average_cost <= 0:
            continue
        stop_trigger = position.average_cost * (1 - stop_loss_pct / 100.0)
        take_trigger = position.average_cost * (1 + take_profit_pct / 100.0)
        reason = None
        if mark <= stop_trigger:
            reason = "stop_loss"
        elif mark >= take_trigger:
            reason = "take_profit"
        if reason:
            fill = portfolio.execute(symbol, "sell", position.quantity, mark, reason=reason)
            store.add_order(symbol, fill.side, fill.quantity, fill.price, fill.fee, fill.realized_pnl, fill.reason)
            events.append(f"Auto-exit {symbol}: {reason.replace('_', ' ')} at ${fill.price:,.2f} for {fill.quantity} shares")
    return events


def market_state_for_symbol(symbol: str, period: str, interval: str, horizon: int, round_trip_cost: float) -> dict[str, Any]:
    bars = load_market_data(symbol, period, interval)
    features = build_features(bars, horizon=horizon)
    model = train_model(features)
    predicted_return = float(model.predict(features.iloc[[-1]])[0])
    signal = make_signal(predicted_return, round_trip_cost=round_trip_cost)
    return {
        "bars": bars,
        "features": features,
        "model": model,
        "price": float(bars["Close"].iloc[-1]),
        "predicted_return": predicted_return,
        "signal": signal,
    }


def get_portfolio(starting_cash: float, commission_rate: float, slippage_rate: float) -> PaperPortfolio:
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = PaperPortfolio(starting_cash, commission_rate, slippage_rate)
    return st.session_state.portfolio


def get_store() -> Store:
    if "store" not in st.session_state:
        st.session_state.store = Store("paper_trading.db")
    return st.session_state.store


st.markdown(
        """
        <div class="hero">
            <h1>Paper Market Lab</h1>
            <p>Research-grade signal monitoring with simulated execution, portfolio controls, and holdout backtesting.</p>
            <span class="status-chip">Simulation Only · No Broker Routing</span>
        </div>
        """,
        unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Session Controls")
    watchlist_raw = st.text_input("Watchlist", value="MSFT, AAPL, GOOGL")
    watchlist = parse_watchlist(watchlist_raw)
    period = st.selectbox("History window", ["5d", "10d", "30d", "60d", "3mo", "6mo"], index=3)
    interval = st.selectbox("Interval", ["5m", "15m", "30m", "1h"], index=0)
    horizon = st.slider("Forecast horizon (bars)", min_value=1, max_value=48, value=12)
    starting_cash = st.number_input("Starting cash", min_value=1_000.0, value=100_000.0, step=1_000.0)
    commission_rate = st.number_input("Commission rate", min_value=0.0, max_value=0.05, value=0.001, step=0.0005, format="%.4f")
    slippage_rate = st.number_input("Slippage rate", min_value=0.0, max_value=0.05, value=0.0005, step=0.0005, format="%.4f")
    st.divider()
    st.subheader("Risk Automation")
    automation_enabled = st.toggle("Enable stop-loss / take-profit", value=False)
    stop_loss_pct = st.slider("Stop-loss %", min_value=0.5, max_value=20.0, value=2.0, step=0.5)
    take_profit_pct = st.slider("Take-profit %", min_value=0.5, max_value=30.0, value=4.0, step=0.5)
    st.caption("Tip: For 5m/15m/30m intervals, keep history up to 60d for Yahoo intraday coverage.")

selected_period = effective_period(period, interval)
if selected_period != period:
    st.info(f"Period auto-adjusted to {selected_period} for {interval} interval Yahoo limits.")

portfolio = get_portfolio(starting_cash, commission_rate, slippage_rate)
store = get_store()
round_trip_cost = commission_rate * 2 + slippage_rate * 2

available: dict[str, dict[str, Any]] = {}
unavailable: dict[str, str] = {}
for symbol in watchlist:
    try:
        available[symbol] = market_state_for_symbol(symbol, selected_period, interval, horizon, round_trip_cost)
    except (MarketDataError, ValueError) as exc:
        unavailable[symbol] = str(exc)

if not available:
    st.error("None of the watchlist symbols returned usable data. Update symbols or interval/window.")
    for symbol, error in unavailable.items():
        st.caption(f"{symbol}: {error}")
    st.stop()

for symbol, error in unavailable.items():
    st.warning(f"{symbol} skipped: {error}")

prices = {symbol: state["price"] for symbol, state in available.items()}
automation_events = apply_risk_automation(portfolio, store, prices, stop_loss_pct, take_profit_pct, automation_enabled)
for event in automation_events:
    st.success(event)

primary_symbol = next(iter(available.keys()))
primary_state = available[primary_symbol]
portfolio_summary = portfolio.summary(prices)

signal_rows = []
for symbol, state in available.items():
    signal_rows.append(
        {
            "symbol": symbol,
            "price": state["price"],
            "signal": state["signal"].action,
            "predicted_return_pct": state["predicted_return"] * 100,
            "net_edge_pct": state["signal"].net_edge * 100,
            "confidence": state["signal"].confidence,
        }
    )
signal_table = pd.DataFrame(signal_rows).sort_values("symbol")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Tracked symbols", str(len(available)))
col2.metric("Reference symbol", primary_symbol)
col3.metric("Reference price", f"${primary_state['price']:,.2f}")
col4.metric("Portfolio P&L", f"${portfolio_summary['pnl']:,.2f}", f"{portfolio_summary['return_pct']:.2f}%")

st.markdown(
    f"<div class='mono'>Watchlist {', '.join(available.keys())} | Period {selected_period} | Interval {interval} | Horizon {horizon} bars</div>",
    unsafe_allow_html=True,
)

tab_dashboard, tab_model, tab_trade, tab_backtest = st.tabs(["Dashboard", "Model Health", "Paper Trading", "Backtest"])

with tab_dashboard:
    left, right = st.columns([1, 2])
    with left:
        st.markdown("<div class='section-title'>Portfolio Snapshot</div>", unsafe_allow_html=True)
        summary_df = pd.DataFrame([portfolio.summary(prices)])
        st.dataframe(
            summary_df,
            width="stretch",
            hide_index=True,
            column_config={
                "cash": st.column_config.NumberColumn("Cash", format="$%.2f"),
                "equity": st.column_config.NumberColumn("Equity", format="$%.2f"),
                "pnl": st.column_config.NumberColumn("PnL", format="$%.2f"),
                "return_pct": st.column_config.NumberColumn("Return %", format="%.2f%%"),
            },
        )
        st.markdown("<div class='section-title'>Watchlist Signals</div>", unsafe_allow_html=True)
        st.dataframe(
            signal_table,
            width="stretch",
            hide_index=True,
            column_config={
                "symbol": st.column_config.TextColumn("Symbol"),
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "signal": st.column_config.TextColumn("Signal"),
                "predicted_return_pct": st.column_config.NumberColumn("Predicted %", format="%.3f%%"),
                "net_edge_pct": st.column_config.NumberColumn("Net Edge %", format="%.3f%%"),
                "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
            },
        )
    with right:
        chart_symbol = st.selectbox("Chart symbol", list(available.keys()), index=0)
        st.markdown("<div class='section-title'>Price And Volume</div>", unsafe_allow_html=True)
        render_candles_with_volume(available[chart_symbol]["bars"], chart_symbol)

with tab_model:
    st.markdown("<div class='section-title'>Model Metrics By Symbol</div>", unsafe_allow_html=True)
    model_rows = []
    for symbol, state in available.items():
        metrics = state["model"].metrics
        model_rows.append(
            {
                "symbol": symbol,
                "rmse": metrics["rmse"],
                "mae": metrics["mae"],
                "direction_pct": metrics["directional_accuracy"] * 100,
                "strategy_return_pct": metrics["strategy_return"] * 100,
            }
        )
    model_table = pd.DataFrame(model_rows).sort_values("symbol")
    st.dataframe(
        model_table,
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Symbol"),
            "rmse": st.column_config.NumberColumn("RMSE", format="%.5f"),
            "mae": st.column_config.NumberColumn("MAE", format="%.5f"),
            "direction_pct": st.column_config.NumberColumn("Direction %", format="%.2f%%"),
            "strategy_return_pct": st.column_config.NumberColumn("Strategy Return %", format="%.2f%%"),
        },
    )
    model_symbol = st.selectbox("Validation detail symbol", list(available.keys()), index=0)
    try:
        wf_scores = walk_forward_scores(available[model_symbol]["features"])
        st.markdown("<div class='section-title'>Walk-Forward Validation</div>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(wf_scores), width="stretch", hide_index=True)
    except ValueError as exc:
        st.info(f"Walk-forward skipped: {exc}")

with tab_trade:
    left, right = st.columns([1, 1])
    tradable_symbols = sorted(set(list(available.keys()) + list(portfolio.positions.keys())))
    selected_trade_symbol = st.selectbox("Trade symbol", tradable_symbols, index=0)
    selected_trade_price = prices.get(selected_trade_symbol, primary_state["price"])
    with left:
        st.markdown("<div class='section-title'>Place Paper Order</div>", unsafe_allow_html=True)
        with st.form("order_form"):
            side = st.selectbox("Side", ["buy", "sell"])
            order_mode = st.selectbox("Order mode", ["Market (latest close)", "Manual price"])
            allocation_pct = st.slider("Buy allocation % of cash", min_value=1, max_value=100, value=10, step=1)
            if order_mode == "Manual price":
                price = st.number_input("Fill price", min_value=0.01, value=float(selected_trade_price), step=0.01)
            else:
                price = float(selected_trade_price)
                st.caption(f"Market fill will use latest close: ${price:,.2f}")
            suggested_qty = max(int((portfolio.cash * (allocation_pct / 100.0)) / max(price, 0.01)), 1)
            quantity = st.number_input("Quantity", min_value=1, value=suggested_qty, step=1)
            submit = st.form_submit_button("Submit Order")
        if submit:
            try:
                fill = portfolio.execute(selected_trade_symbol, side, int(quantity), float(price), reason="manual")
                store.add_order(selected_trade_symbol, fill.side, fill.quantity, fill.price, fill.fee, fill.realized_pnl, fill.reason)
                st.success("Paper order recorded")
            except TradingError as exc:
                st.error(str(exc))

        position = portfolio.positions.get(selected_trade_symbol)
        if position and position.quantity > 0:
            if st.button(f"Sell All {selected_trade_symbol}"):
                try:
                    fill = portfolio.execute(selected_trade_symbol, "sell", position.quantity, selected_trade_price, reason="manual_close")
                    store.add_order(selected_trade_symbol, fill.side, fill.quantity, fill.price, fill.fee, fill.realized_pnl, fill.reason)
                    st.success("Position closed")
                except TradingError as exc:
                    st.error(str(exc))

        st.markdown("<div class='section-title'>Open Positions</div>", unsafe_allow_html=True)
        positions_df = position_table(portfolio, prices)
        if not positions_df.empty:
            st.dataframe(
                positions_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "Avg Cost": st.column_config.NumberColumn(format="$%.2f"),
                    "Mark": st.column_config.NumberColumn(format="$%.2f"),
                    "Market Value": st.column_config.NumberColumn(format="$%.2f"),
                    "Cost Basis": st.column_config.NumberColumn(format="$%.2f"),
                    "Unrealized PnL": st.column_config.NumberColumn(format="$%.2f"),
                    "Unrealized %": st.column_config.NumberColumn(format="%.2f%%"),
                    "Realized PnL": st.column_config.NumberColumn(format="$%.2f"),
                },
            )
        else:
            st.info("No open positions.")
    with right:
        st.markdown("<div class='section-title'>Trade Blotter</div>", unsafe_allow_html=True)
        orders = store.orders()
        if orders:
            blotter = format_orders_table(orders)
            c1, c2, c3 = st.columns(3)
            symbol_filter = c1.multiselect("Symbol filter", sorted(blotter["Symbol"].unique().tolist()), default=sorted(blotter["Symbol"].unique().tolist()))
            side_filter = c2.selectbox("Side filter", ["all", "buy", "sell"], index=0)
            reason_filter = c3.selectbox("Reason filter", ["all"] + sorted(blotter["Reason"].astype(str).str.lower().unique().tolist()), index=0)

            filtered = blotter[blotter["Symbol"].isin(symbol_filter)]
            if side_filter != "all":
                filtered = filtered[filtered["Side"].str.lower() == side_filter]
            if reason_filter != "all":
                filtered = filtered[filtered["Reason"].str.lower() == reason_filter]

            realized_total = float(filtered["Realized PnL"].sum())
            winners = int((filtered["Realized PnL"] > 0).sum())
            losers = int((filtered["Realized PnL"] < 0).sum())
            stats = st.columns(3)
            stats[0].metric("Realized PnL", f"${realized_total:,.2f}")
            stats[1].metric("Winning exits", str(winners))
            stats[2].metric("Losing exits", str(losers))

            st.dataframe(
                filtered,
                width="stretch",
                hide_index=True,
                column_config={
                    "Fill Price": st.column_config.NumberColumn(format="$%.2f"),
                    "Fee": st.column_config.NumberColumn(format="$%.2f"),
                    "Realized PnL": st.column_config.NumberColumn(format="$%.2f"),
                },
            )
        else:
            st.info("No orders yet.")

with tab_backtest:
    st.markdown("<div class='section-title'>Holdout Backtest</div>", unsafe_allow_html=True)
    backtest_symbol = st.selectbox("Backtest symbol", list(available.keys()), index=0)
    if st.button("Run Backtest"):
        backtest_state = available[backtest_symbol]
        split = int(len(backtest_state["features"]) * 0.8)
        holdout_features = backtest_state["features"].iloc[split:]
        holdout_bars = backtest_state["bars"].loc[holdout_features.index]
        predictions = pd.Series(backtest_state["model"].predict(holdout_features), index=holdout_features.index)
        report = run_backtest(backtest_symbol, holdout_bars, predictions, starting_cash, commission_rate, slippage_rate)
        equity_curve = report["equity_curve"]
        export = holdout_bars.loc[equity_curve.index].copy()
        export["symbol"] = backtest_symbol
        export["predicted_return"] = predictions.loc[equity_curve.index]
        export["signal"] = export["predicted_return"].apply(lambda value: make_signal(float(value), round_trip_cost=round_trip_cost).action)
        export["equity"] = equity_curve
        export["equity_return_pct"] = (export["equity"] / starting_cash - 1) * 100
        export["drawdown_pct"] = (export["equity"] / export["equity"].cummax() - 1) * 100
        st.session_state["last_backtest_csv"] = export.reset_index().to_csv(index=False).encode("utf-8")
        st.session_state["last_backtest_symbol"] = backtest_symbol
        summary = report["summary"]
        metric_row = st.columns(3)
        metric_row[0].metric("Return", f"{summary['total_return_pct']:.2f}%")
        metric_row[1].metric("Max Drawdown", f"{summary['max_drawdown_pct']:.2f}%")
        metric_row[2].metric("Trades", str(summary['trades']))
        curve = pd.DataFrame({"timestamp": equity_curve.index, "equity": equity_curve.values, "drawdown_pct": export["drawdown_pct"].values})
        figure = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
        figure.add_trace(
            go.Scatter(
                x=curve["timestamp"],
                y=curve["equity"],
                mode="lines",
                line={"color": "#22c55e", "width": 2.2},
                name="Equity",
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=curve["timestamp"],
                y=curve["drawdown_pct"],
                mode="lines",
                line={"color": "#f43f5e", "width": 1.7},
                fill="tozeroy",
                fillcolor="rgba(244,63,94,0.25)",
                name="Drawdown %",
            ),
            row=2,
            col=1,
        )
        figure.update_layout(
            title=f"{backtest_symbol} Equity And Drawdown",
            height=460,
            margin={"l": 10, "r": 10, "t": 45, "b": 10},
            paper_bgcolor="#07130d",
            plot_bgcolor="#07130d",
            font={"color": "#d8ffe4", "family": "Space Grotesk"},
            legend={"orientation": "h", "y": 1.03, "x": 0.02},
        )
        figure.update_xaxes(showgrid=True, gridcolor="#123322", zeroline=False)
        figure.update_yaxes(showgrid=True, gridcolor="#123322", zeroline=False)
        st.plotly_chart(figure, width="stretch")

    if "last_backtest_csv" in st.session_state:
        st.download_button(
            "Download Backtest CSV",
            data=st.session_state["last_backtest_csv"],
            file_name=f"{st.session_state.get('last_backtest_symbol', 'watchlist').lower()}_backtest_report.csv",
            mime="text/csv",
        )

if st.sidebar.button("Reset Paper Portfolio"):
    st.session_state.pop("portfolio", None)
    st.success("Paper portfolio reset. Refresh to continue.")
