from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..services import PaperRebalancePlan, PortfolioAttribution, SymbolStrategyStats


PANEL = "rgba(8, 17, 36, 0.0)"
TEXT = "#eaf1ff"
GRID = "rgba(128, 163, 235, 0.10)"
BLUE = "#60a5fa"
GREEN = "#34d399"
RED = "#fb7185"


def attribution_frame(report: PortfolioAttribution) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Symbol": row.symbol,
            "Realized P&L": row.realized_pnl,
            "Unrealized P&L": row.unrealized_pnl,
            "Total P&L": row.total_pnl,
            "Fees": row.fees,
            "Orders": row.orders,
            "Gross contribution %": row.gross_contribution_pct,
        }
        for row in report.symbols
    ])


def render_attribution(report: PortfolioAttribution) -> None:
    frame = attribution_frame(report)
    if frame.empty:
        st.info("Performance attribution appears after paper orders or open positions exist.")
        return
    colors = [GREEN if value >= 0 else RED for value in frame["Total P&L"]]
    figure = go.Figure(go.Bar(
        x=frame["Symbol"],
        y=frame["Total P&L"],
        marker_color=colors,
        text=[f"${value:,.0f}" for value in frame["Total P&L"]],
        textposition="outside",
        hovertemplate="%{x}<br>Total P&L $%{y:,.2f}<extra></extra>",
    ))
    figure.update_layout(
        height=360,
        margin={"l": 12, "r": 12, "t": 44, "b": 12},
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font={"color": TEXT, "family": "Inter, system-ui, sans-serif"},
        title={"text": "P&L attribution by symbol", "x": 0.01},
        yaxis_title="Attributed P&L ($)",
        showlegend=False,
    )
    figure.update_xaxes(showgrid=False, zeroline=False)
    figure.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=True, zerolinecolor=BLUE)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False, "responsive": True})
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Realized P&L": st.column_config.NumberColumn(format="$%.2f"),
            "Unrealized P&L": st.column_config.NumberColumn(format="$%.2f"),
            "Total P&L": st.column_config.NumberColumn(format="$%.2f"),
            "Fees": st.column_config.NumberColumn(format="$%.2f"),
            "Gross contribution %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )


def symbol_stats_frame(rows: list[SymbolStrategyStats]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Symbol": row.symbol,
            "Decisions": row.decisions,
            "Executed": row.executed_decisions,
            "Rejected": row.rejected_decisions,
            "Model gate pass": row.model_gate_pass_rate,
            "Avg confidence": row.average_confidence,
            "Avg net edge": row.average_net_edge,
            "Closed trades": row.closed_trades,
            "Win rate": row.win_rate,
            "Realized P&L": row.realized_pnl,
            "Expectancy": row.expectancy,
        }
        for row in rows
    ])


def render_symbol_stats(rows: list[SymbolStrategyStats]) -> None:
    frame = symbol_stats_frame(rows)
    if frame.empty:
        st.info("No per-symbol strategy statistics are available yet.")
        return
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "Model gate pass": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.0f%%"),
            "Avg confidence": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.0f%%"),
            "Avg net edge": st.column_config.NumberColumn(format="%+.4f"),
            "Win rate": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.0f%%"),
            "Realized P&L": st.column_config.NumberColumn(format="$%.2f"),
            "Expectancy": st.column_config.NumberColumn(format="$%.2f"),
        },
    )


def rebalance_frame(plan: PaperRebalancePlan) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Symbol": item.symbol,
            "Side": item.side.upper(),
            "Quantity": item.quantity,
            "Price": item.price,
            "Estimated value": item.estimated_value,
            "Current %": item.current_pct,
            "Target %": item.target_pct,
            "Reason": item.reason,
        }
        for item in plan.instructions
    ])
