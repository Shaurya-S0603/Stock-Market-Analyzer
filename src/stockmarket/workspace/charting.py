"""Interactive multi-panel Plotly financial chart with shared, causal indicator functions."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import indicators as ind
from .research_storage import validate_chart

PANEL_INDICATORS = ["RSI", "MACD", "Stochastic", "ATR", "ROC", "OBV"]


def build_chart(frame: pd.DataFrame, config: dict) -> go.Figure:
    chart = validate_chart(config)
    if frame.empty:
        raise ValueError("Load actual historical bars before charting")
    requested = chart["indicators"]
    if "VWAP" in requested and chart["interval"] not in {"1m", "5m", "15m", "1h"}:
        raise ValueError("UTC-date VWAP requires intraday data; switch chart interval")
    extra = [name for name in PANEL_INDICATORS if name in requested]
    volume = chart["volume"]
    subtitles = ["Price"] + (["Volume"] if volume else []) + extra
    heights = [0.5] + ([0.15] if volume else []) + [0.14 for _ in extra]
    heights = [n / sum(heights) for n in heights]
    figure = make_subplots(rows=len(subtitles), cols=1, shared_xaxes=True, vertical_spacing=.025,
                           row_heights=heights, subplot_titles=subtitles)
    x = frame.index
    typ = chart["chart_type"]
    if typ == "Candles":
        figure.add_trace(go.Candlestick(
            x=x, open=frame["open"], high=frame["high"], low=frame["low"],
            close=frame["close"], name="Price",
        ), row=1, col=1)
    elif typ == "OHLC":
        figure.add_trace(go.Ohlc(
            x=x, open=frame["open"], high=frame["high"], low=frame["low"],
            close=frame["close"], name="Price",
        ), row=1, col=1)
    elif typ == "Area":
        figure.add_trace(go.Scatter(x=x, y=frame["close"], mode="lines", name="Close", fill="tozeroy"), row=1, col=1)
    else:
        figure.add_trace(go.Scatter(x=x, y=frame["close"], mode="lines", name="Close"), row=1, col=1)

    n = chart["length"]
    for name, func in (("SMA", ind.sma), ("EMA", ind.ema), ("WMA", ind.wma)):
        if name in requested:
            series = func(frame, n)
            figure.add_trace(go.Scatter(x=x, y=series, name=series.name, mode="lines"), row=1, col=1)
    if "Bollinger" in requested:
        band = ind.bollinger(frame, n, chart["bollinger_std"])
        for name in ["Lower", "Middle", "Upper"]:
            figure.add_trace(go.Scatter(x=x, y=band[name], name="BB " + name,
                                        mode="lines", line={"dash": "dot"}), row=1, col=1)
    if "Breakout" in requested:
        prior = ind.breakout_levels(frame, n)
        for name in prior:
            figure.add_trace(go.Scatter(x=x, y=prior[name], name=name, mode="lines",
                                        line={"dash": "dash"}), row=1, col=1)
    if "VWAP" in requested:
        series = ind.vwap_utc_day(frame)
        figure.add_trace(go.Scatter(x=x, y=series, name="UTC-date VWAP", mode="lines"), row=1, col=1)

    row = 2
    if volume:
        figure.add_trace(go.Bar(x=x, y=frame["volume"], name="Volume", opacity=.5), row=row, col=1)
        row += 1
    for name in extra:
        if name == "RSI":
            series = ind.rsi(frame, chart["rsi_length"])
            figure.add_trace(go.Scatter(x=x, y=series, name=series.name), row=row, col=1)
            figure.add_hline(y=70, line_dash="dash", line_width=1, row=row, col=1)
            figure.add_hline(y=30, line_dash="dash", line_width=1, row=row, col=1)
            figure.update_yaxes(range=[0, 100], row=row, col=1)
        elif name == "MACD":
            indicator = ind.macd(frame)
            for column in ("MACD", "Signal"):
                figure.add_trace(go.Scatter(x=x, y=indicator[column], name=column), row=row, col=1)
            figure.add_trace(go.Bar(x=x, y=indicator["Histogram"], name="MACD Histogram"), row=row, col=1)
        elif name == "Stochastic":
            indicator = ind.stochastic(frame, chart["rsi_length"])
            for column in ("%K", "%D"):
                figure.add_trace(go.Scatter(x=x, y=indicator[column], name="Stochastic "+column), row=row, col=1)
            figure.update_yaxes(range=[0, 100], row=row, col=1)
        else:
            series = {"ATR": lambda: ind.atr(frame, chart["rsi_length"]),
                      "ROC": lambda: ind.roc(frame, chart["rsi_length"]),
                      "OBV": lambda: ind.obv(frame)}[name]()
            figure.add_trace(go.Scatter(x=x, y=series, name=series.name), row=row, col=1)
        row += 1
    figure.update_layout(
        template="plotly_dark", height=max(480, 335 + 135 * (len(subtitles)-1)),
        hovermode="x unified", title=f"{chart['symbol']} · {chart['interval']} · historical data",
        xaxis_rangeslider_visible=False, margin=dict(l=35, r=25, t=85, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.06),
    )
    figure.update_xaxes(rangeslider_visible=False)
    figure.update_yaxes(fixedrange=False)
    return figure
