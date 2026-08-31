from __future__ import annotations

import pandas as pd
import streamlit as st

from ..services import AnalysisRequest, AnalysisService, PortfolioService, SymbolAnalysis
from ..storage import Store
from ..trading import PaperPortfolio, TradingError
from .charts import render_equity_curve, render_price_chart
from .components import callout, kpi_grid, section_header
from .tables import model_table, orders_table, positions_table, signal_table


def render_dashboard(available: dict[str, SymbolAnalysis], portfolio: PaperPortfolio, prices: dict[str, float]) -> None:
    summary = portfolio.summary(prices)
    st.subheader("Portfolio snapshot")
    cols = st.columns(4)
    cols[0].metric("Cash", f"${summary['cash']:,.2f}")
    cols[1].metric("Equity", f"${summary['equity']:,.2f}")
    cols[2].metric("P&L", f"${summary['pnl']:,.2f}")
    cols[3].metric("Return", f"{summary['return_pct']:.2f}%")

    st.subheader("Watchlist signals")
    table = signal_table(available)
    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Symbol"),
            "price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "signal": st.column_config.TextColumn("Signal"),
            "predicted_return_pct": st.column_config.NumberColumn("Predicted return", format="%.3f%%"),
            "net_edge_pct": st.column_config.NumberColumn("Net edge", format="%.3f%%"),
            "confidence": st.column_config.ProgressColumn("Confidence", min_value=0.0, max_value=1.0, format="%.0f%%"),
            "as_of": st.column_config.DatetimeColumn("Data as of"),
        },
    )
    st.caption("Buy, Sell, and Hold are rule-based labels from predicted return after estimated round-trip trading costs.")

    st.subheader("Price and volume")
    chart_symbol = st.selectbox("Chart symbol", list(available), index=0, key="dashboard_chart_symbol")
    render_price_chart(available[chart_symbol].bars, chart_symbol)


def render_model_health(available: dict[str, SymbolAnalysis], analysis_service: AnalysisService) -> None:
    section_header("Model health", "Historical diagnostics are governance evidence, not future-return guarantees")
    table = model_table(available)
    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        column_config={
            "symbol": st.column_config.TextColumn("Symbol"),
            "rmse": st.column_config.NumberColumn("RMSE", format="%.5f"),
            "mae": st.column_config.NumberColumn("MAE", format="%.5f"),
            "directional_accuracy": st.column_config.NumberColumn("Direction accuracy", format="%.2f"),
            "strategy_return": st.column_config.NumberColumn("Positive-signal return", format="%.4f"),
            "baseline_rmse": st.column_config.NumberColumn("Zero-return RMSE", format="%.5f"),
        },
    )

    section_header("Validation detail", "Purged expanding windows and identical benchmark folds")
    symbol = st.selectbox("Validation symbol", list(available), index=0, key="validation_symbol")
    try:
        scores = analysis_service.validation_scores(available[symbol])
        benchmark_rows, gate = analysis_service.benchmark_report(available[symbol])
    except ValueError as exc:
        st.info(f"Validation skipped: {exc}")
        return

    walk = pd.DataFrame(scores)
    benchmark_frame = pd.DataFrame(benchmark_rows).sort_values(["rmse", "complexity_rank"])
    candidate = benchmark_frame.loc[benchmark_frame["model"] == "ridge_momentum"].iloc[0]
    best = benchmark_frame.iloc[0]
    kpi_grid([
        {"label":"Evidence gate","value":"PASS" if gate.approved else "HOLD","delta":gate.reason,"tone":"positive" if gate.approved else "warning","icon":"✓" if gate.approved else "!"},
        {"label":"Candidate RMSE","value":f"{float(candidate['rmse']):.5f}","delta":"Ridge + momentum","tone":"blue","icon":"μ"},
        {"label":"Direction accuracy","value":f"{float(candidate['directional_accuracy']):.1%}","delta":f"Best RMSE · {best['model']}","tone":"positive" if float(candidate['directional_accuracy']) >= .5 else "warning","icon":"◎"},
        {"label":"Walk-forward folds","value":str(len(walk)),"delta":f"Purge gap · {available[symbol].horizon} bars","tone":"blue","icon":"#"},
    ])
    left, right = st.columns([1, 1.15])
    with left:
        with st.container(border=True):
            st.markdown("#### Purged walk-forward folds")
            st.dataframe(walk, width="stretch", hide_index=True)
    with right:
        with st.container(border=True):
            st.markdown("#### Benchmark ladder")
            st.dataframe(benchmark_frame, width="stretch", hide_index=True)
    callout("Complexity rule", "The AI Trader requires the model evidence gate to pass before an entry can be considered. Passing the gate still does not bypass signal, confidence, or portfolio-risk controls.")


def render_trading(
    available: dict[str, SymbolAnalysis],
    portfolio: PaperPortfolio,
    portfolio_service: PortfolioService,
    store: Store,
    prices: dict[str, float],
) -> None:
    st.subheader("Place paper order")
    tradable = sorted(set(available) | set(portfolio.positions))
    symbol = st.selectbox("Trade symbol", tradable, index=0, key="trade_symbol")
    reference_price = prices.get(symbol, next(iter(prices.values())))

    left, right = st.columns([1, 1])
    with left:
        with st.form("order_form"):
            side = st.selectbox("Side", ["buy", "sell"], format_func=str.title)
            price_mode = st.selectbox("Order price", ["Latest close", "Manual price"])
            allocation = st.slider("Buy allocation of available cash (%)", 1, 100, 10, 1)
            if price_mode == "Manual price":
                price = st.number_input("Fill price", min_value=0.01, value=float(reference_price), step=0.01)
            else:
                price = float(reference_price)
                st.caption(f"Latest-close reference: ${price:,.2f}")
            suggested = max(int((portfolio.cash * allocation / 100.0) / max(float(price), 0.01)), 1)
            quantity = st.number_input("Quantity", min_value=1, value=suggested, step=1)
            submitted = st.form_submit_button("Submit paper order", use_container_width=True)
        if submitted:
            try:
                fill = portfolio_service.execute(symbol, side, int(quantity), float(price))
                st.success(f"Recorded {fill.side} {fill.quantity} {symbol} at ${fill.price:,.2f}.")
                st.rerun()
            except TradingError as exc:
                st.error(str(exc))

        position = portfolio.positions.get(symbol)
        if position and position.quantity > 0 and st.button(f"Close all {symbol}", use_container_width=True):
            try:
                fill = portfolio_service.execute(symbol, "sell", position.quantity, reference_price, reason="manual_close")
                st.success(f"Closed {fill.quantity} shares of {symbol} at ${fill.price:,.2f}.")
                st.rerun()
            except TradingError as exc:
                st.error(str(exc))

    with right:
        st.subheader("Open positions")
        positions = positions_table(portfolio, prices)
        if positions.empty:
            st.info("No open paper positions.")
        else:
            st.dataframe(positions, width="stretch", hide_index=True)

    st.subheader("Order history")
    orders = orders_table(store.orders())
    if orders.empty:
        st.info("No paper orders recorded yet.")
    else:
        st.dataframe(orders, width="stretch", hide_index=True)


def render_backtest(
    available: dict[str, SymbolAnalysis],
    analysis_service: AnalysisService,
    request: AnalysisRequest,
    starting_cash: float,
) -> None:
    section_header("Backtest configuration", "The model is trained only on information available before the purged holdout")
    symbol = st.selectbox("Backtest symbol", list(available), index=0, key="backtest_symbol")
    try:
        report = analysis_service.backtest(available[symbol], request, starting_cash)
    except ValueError as exc:
        st.info(f"Backtest unavailable: {exc}")
        return
    summary = report["summary"]
    kpi_grid([
        {"label":"Strategy return","value":f"{summary['total_return_pct']:+.2f}%","delta":f"Buy & hold {summary['buy_hold_return_pct']:+.2f}%","tone":"positive" if summary['total_return_pct'] >= 0 else "negative","icon":"↗"},
        {"label":"Excess return","value":f"{summary['excess_vs_buy_hold_pct']:+.2f}%","delta":"Strategy minus benchmark","tone":"positive" if summary['excess_vs_buy_hold_pct'] >= 0 else "negative","icon":"Δ"},
        {"label":"Max drawdown","value":f"{summary['max_drawdown_pct']:.2f}%","delta":f"Exposure {summary['exposure_pct']:.1f}%","tone":"warning" if summary['max_drawdown_pct'] < -5 else "blue","icon":"↓"},
        {"label":"Risk-adjusted score","value":f"{summary['risk_adjusted_score']:.2f}","delta":f"Hit rate {summary['hit_rate_pct']:.1f}%","tone":"positive" if summary['risk_adjusted_score'] > 0 else "warning","icon":"◎"},
    ])
    detail = st.columns(4)
    detail[0].metric("Executions", str(summary["trades"]))
    detail[1].metric("Round trips", str(summary["round_trips"]))
    detail[2].metric("Turnover", f"{summary['turnover_pct']:.1f}%")
    detail[3].metric("Exposure", f"{summary['exposure_pct']:.1f}%")
    with st.container(border=True):
        render_equity_curve(report["equity_curve"], symbol)
    callout("Backtest integrity", "Signals are generated on unseen holdout rows and executed on the following bar's open. Commission and slippage assumptions are included. The risk-adjusted score is sample-scaled rather than annualized.")
