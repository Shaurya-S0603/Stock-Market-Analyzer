from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


def render_price_chart(bars: pd.DataFrame, symbol: str) -> None:
    if bars.empty:
        st.info("No price bars are available for this symbol.")
        return
    frame = bars.tail(300).copy()
    frame["ema_20"] = frame["Close"].ewm(span=20, adjust=False).mean()
    volume_colors = ["#43d17b" if c >= o else "#ff7a8d" for o, c in zip(frame["Open"], frame["Close"])]
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.72,0.28])
    figure.add_trace(go.Candlestick(x=frame.index,open=frame["Open"],high=frame["High"],low=frame["Low"],close=frame["Close"],increasing_line_color="#43d17b",decreasing_line_color="#ff7a8d",name="Price"),row=1,col=1)
    figure.add_trace(go.Scatter(x=frame.index,y=frame["ema_20"],mode="lines",name="EMA 20",line={"color":"#8ce8ae","width":2}),row=1,col=1)
    figure.add_trace(go.Bar(x=frame.index,y=frame["Volume"],marker={"color":volume_colors},name="Volume",opacity=0.82),row=2,col=1)
    figure.update_layout(title={"text":f"{symbol} price and volume","x":0.02},height=560,margin={"l":10,"r":10,"t":50,"b":10},paper_bgcolor="#0d1b12",plot_bgcolor="#0d1b12",font={"color":"#f1f7f3","family":"Inter, system-ui, sans-serif"},xaxis_rangeslider_visible=False,hovermode="x unified",legend={"orientation":"h","y":1.03,"x":0.02})
    figure.update_xaxes(showgrid=True,gridcolor="#1f392b",zeroline=False)
    figure.update_yaxes(showgrid=True,gridcolor="#1f392b",zeroline=False)
    st.plotly_chart(figure,width="stretch",config={"displayModeBar":False,"responsive":True})
    latest = frame.iloc[-1]
    st.caption(f"Chart summary: latest close ${latest['Close']:,.2f}; EMA 20 ${latest['ema_20']:,.2f}; volume {latest['Volume']:,.0f}. The chart is historical market data, not an execution feed.")


def render_equity_curve(equity: pd.Series, symbol: str) -> None:
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=equity.index,y=equity.values,mode="lines",name="Paper equity",line={"width":2}))
    figure.update_layout(title=f"{symbol} backtest equity curve",xaxis_title="Time",yaxis_title="Equity ($)",height=420,margin={"l":10,"r":10,"t":50,"b":10},paper_bgcolor="#0d1b12",plot_bgcolor="#0d1b12",font={"color":"#f1f7f3"})
    st.plotly_chart(figure,width="stretch",config={"displayModeBar":False,"responsive":True})
