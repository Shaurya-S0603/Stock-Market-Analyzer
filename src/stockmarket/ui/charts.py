from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

PANEL = "rgba(8, 17, 36, 0.0)"
TEXT = "#eaf1ff"
GRID = "rgba(128, 163, 235, 0.10)"
BLUE = "#60a5fa"
CYAN = "#38bdf8"
GREEN = "#34d399"
RED = "#fb7185"
MUTED = "#7f8ead"


def _layout(figure: go.Figure, height: int = 420) -> None:
    figure.update_layout(
        height=height,
        margin={"l": 12, "r": 12, "t": 44, "b": 12},
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font={"color": TEXT, "family": "Inter, system-ui, sans-serif"},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.04, "x": 0.01},
    )
    figure.update_xaxes(showgrid=True, gridcolor=GRID, zeroline=False)
    figure.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False)


def render_price_chart(bars: pd.DataFrame, symbol: str) -> None:
    if bars.empty:
        st.info("No price bars are available for this symbol.")
        return
    frame = bars.tail(300).copy()
    frame["ema_20"] = frame["Close"].ewm(span=20, adjust=False).mean()
    volume_colors = [GREEN if c >= o else RED for o, c in zip(frame["Open"], frame["Close"])]
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.72, 0.28])
    figure.add_trace(go.Candlestick(x=frame.index, open=frame["Open"], high=frame["High"], low=frame["Low"], close=frame["Close"], increasing_line_color=GREEN, decreasing_line_color=RED, name="Price"), row=1, col=1)
    figure.add_trace(go.Scatter(x=frame.index, y=frame["ema_20"], mode="lines", name="EMA 20", line={"color": CYAN, "width": 2}), row=1, col=1)
    figure.add_trace(go.Bar(x=frame.index, y=frame["Volume"], marker={"color": volume_colors}, name="Volume", opacity=0.72), row=2, col=1)
    _layout(figure, 540)
    figure.update_layout(title={"text": f"{symbol} market structure", "x": 0.01}, xaxis_rangeslider_visible=False)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    latest = frame.iloc[-1]
    st.caption(f"Chart summary: latest close ${latest['Close']:,.2f}; EMA 20 ${latest['ema_20']:,.2f}; volume {latest['Volume']:,.0f}. Historical market data only.")


def render_equity_curve(equity: pd.Series, symbol: str) -> None:
    figure = go.Figure(go.Scatter(x=equity.index, y=equity.values, mode="lines", name="Paper equity", line={"width": 2.2, "color": BLUE}, fill="tozeroy", fillcolor="rgba(59,130,246,.08)"))
    _layout(figure, 410)
    figure.update_layout(title=f"{symbol} backtest equity curve", xaxis_title="Time", yaxis_title="Equity ($)")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})


def render_portfolio_history(snapshots: list[dict]) -> None:
    if not snapshots:
        st.info("Portfolio history appears after AI Trader decision cycles are recorded.")
        return
    frame = pd.DataFrame(list(reversed(snapshots)))
    frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce")
    frame = frame.dropna(subset=["created_at"])
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=frame["created_at"], y=frame["equity"], mode="lines", name="Equity", line={"color": BLUE, "width": 2.2}, fill="tozeroy", fillcolor="rgba(59,130,246,.08)"))
    figure.add_trace(go.Scatter(x=frame["created_at"], y=frame["cash"], mode="lines", name="Cash", line={"color": MUTED, "width": 1.4, "dash": "dot"}))
    _layout(figure, 390)
    figure.update_layout(title={"text":"Paper portfolio history","x":0.01}, yaxis_title="Value ($)")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})


def render_portfolio_allocation(portfolio, prices: dict[str, float]) -> None:
    rows = portfolio.positions_snapshot(prices)
    labels = [row["symbol"] for row in rows]
    values = [row["market_value"] for row in rows]
    if portfolio.cash > 0:
        labels.append("Cash")
        values.append(portfolio.cash)
    if not values:
        st.info("No portfolio allocation to display.")
        return
    figure = go.Figure(go.Pie(labels=labels, values=values, hole=.66, textinfo="label+percent", hovertemplate="%{label}<br>$%{value:,.2f}<br>%{percent}<extra></extra>"))
    _layout(figure, 390)
    figure.update_layout(title={"text":"Portfolio allocation","x":0.01}, showlegend=False)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})


def render_decision_mix(decisions: list[dict]) -> None:
    if not decisions:
        st.info("No AI decision history yet.")
        return
    frame = pd.DataFrame(decisions)
    counts = frame["decision"].value_counts().sort_index()
    figure = go.Figure(go.Bar(x=counts.index, y=counts.values, marker_color=[BLUE] * len(counts), text=counts.values, textposition="outside"))
    _layout(figure, 330)
    figure.update_layout(title={"text":"AI decision mix","x":0.01}, yaxis_title="Decisions", showlegend=False)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
