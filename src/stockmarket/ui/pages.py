from __future__ import annotations

import pandas as pd
import streamlit as st

from ..services import AnalysisRequest, AnalysisService, PortfolioService, SymbolAnalysis
from ..storage import Store
from ..trading import PaperPortfolio, TradingError
from .charts import render_equity_curve, render_price_chart
from .tables import model_table, orders_table, positions_table, signal_table


def render_dashboard(available:dict[str,SymbolAnalysis],portfolio:PaperPortfolio,prices:dict[str,float])->None:
    summary=portfolio.summary(prices); st.subheader("Portfolio snapshot"); cols=st.columns(4); cols[0].metric("Cash",f"${summary['cash']:,.2f}"); cols[1].metric("Equity",f"${summary['equity']:,.2f}"); cols[2].metric("P&L",f"${summary['pnl']:,.2f}"); cols[3].metric("Return",f"{summary['return_pct']:.2f}%")
    st.subheader("Watchlist signals"); st.dataframe(signal_table(available),width="stretch",hide_index=True); st.caption("Buy, Sell, and Hold are rule-based labels from predicted return after estimated round-trip trading costs.")
    st.subheader("Price and volume"); chart_symbol=st.selectbox("Chart symbol",list(available),index=0,key="dashboard_chart_symbol"); render_price_chart(available[chart_symbol].bars,chart_symbol)


def render_model_health(available:dict[str,SymbolAnalysis],analysis_service:AnalysisService)->None:
    st.subheader("Model metrics by symbol"); st.dataframe(model_table(available),width="stretch",hide_index=True); st.caption("These metrics use historical purged holdout data. They are diagnostics, not evidence of future profitability.")
    symbol=st.selectbox("Validation detail symbol",list(available),index=0,key="validation_symbol")
    try:
        scores=analysis_service.validation_scores(available[symbol]); st.subheader("Purged walk-forward validation"); st.dataframe(pd.DataFrame(scores),width="stretch",hide_index=True)
        benchmark_rows,gate=analysis_service.benchmark_report(available[symbol]); st.subheader("Benchmark ladder"); st.dataframe(pd.DataFrame(benchmark_rows).sort_values(["rmse","complexity_rank"]),width="stretch",hide_index=True)
        st.success(f"Model gate passed: {gate.reason}") if gate.approved else st.warning(f"Model gate not passed: {gate.reason}")
        st.caption("The gate does not authorize trading. It only determines whether additional model complexity is justified by out-of-sample evidence.")
    except ValueError as exc: st.info(f"Validation skipped: {exc}")


def render_trading(available:dict[str,SymbolAnalysis],portfolio:PaperPortfolio,portfolio_service:PortfolioService,store:Store,prices:dict[str,float])->None:
    st.subheader("Place paper order"); tradable=sorted(set(available)|set(portfolio.positions)); symbol=st.selectbox("Trade symbol",tradable,index=0,key="trade_symbol"); reference_price=prices.get(symbol,next(iter(prices.values()))); left,right=st.columns([1,1])
    with left:
        with st.form("order_form"):
            side=st.selectbox("Side",["buy","sell"],format_func=str.title); price_mode=st.selectbox("Order price",["Latest close","Manual price"]); allocation=st.slider("Buy allocation of available cash (%)",1,100,10,1); price=st.number_input("Fill price",min_value=0.01,value=float(reference_price),step=0.01) if price_mode=="Manual price" else float(reference_price); suggested=max(int((portfolio.cash*allocation/100.0)/max(float(price),0.01)),1); quantity=st.number_input("Quantity",min_value=1,value=suggested,step=1); submitted=st.form_submit_button("Submit paper order",use_container_width=True)
        if submitted:
            try: fill=portfolio_service.execute(symbol,side,int(quantity),float(price)); st.success(f"Recorded {fill.side} {fill.quantity} {symbol} at ${fill.price:,.2f}."); st.rerun()
            except TradingError as exc: st.error(str(exc))
        position=portfolio.positions.get(symbol)
        if position and position.quantity>0 and st.button(f"Close all {symbol}",use_container_width=True):
            try: fill=portfolio_service.execute(symbol,"sell",position.quantity,reference_price,reason="manual_close"); st.success(f"Closed {fill.quantity} shares of {symbol} at ${fill.price:,.2f}."); st.rerun()
            except TradingError as exc: st.error(str(exc))
    with right:
        st.subheader("Open positions"); positions=positions_table(portfolio,prices); st.info("No open paper positions.") if positions.empty else st.dataframe(positions,width="stretch",hide_index=True)
    st.subheader("Order history"); orders=orders_table(store.orders()); st.info("No paper orders recorded yet.") if orders.empty else st.dataframe(orders,width="stretch",hide_index=True)


def render_backtest(available:dict[str,SymbolAnalysis],analysis_service:AnalysisService,request:AnalysisRequest,starting_cash:float)->None:
    st.subheader("Purged holdout backtest"); symbol=st.selectbox("Backtest symbol",list(available),index=0,key="backtest_symbol")
    try: report=analysis_service.backtest(available[symbol],request,starting_cash)
    except ValueError as exc: st.info(f"Backtest unavailable: {exc}"); return
    summary=report["summary"]; top=st.columns(4); top[0].metric("Strategy return",f"{summary['total_return_pct']:.2f}%"); top[1].metric("Buy & hold",f"{summary['buy_hold_return_pct']:.2f}%"); top[2].metric("Excess return",f"{summary['excess_vs_buy_hold_pct']:.2f}%"); top[3].metric("Max drawdown",f"{summary['max_drawdown_pct']:.2f}%")
    detail=st.columns(5); detail[0].metric("Trades",str(summary["trades"])); detail[1].metric("Hit rate",f"{summary['hit_rate_pct']:.1f}%"); detail[2].metric("Turnover",f"{summary['turnover_pct']:.1f}%"); detail[3].metric("Exposure",f"{summary['exposure_pct']:.1f}%"); detail[4].metric("Risk-adjusted score",f"{summary['risk_adjusted_score']:.2f}")
    render_equity_curve(report["equity_curve"],symbol); st.caption("The backtest trains only on the pre-holdout window, purges the forecast horizon, predicts unseen rows, and executes signals on the following bar's open. The risk-adjusted score is sample-scaled, not annualized.")
