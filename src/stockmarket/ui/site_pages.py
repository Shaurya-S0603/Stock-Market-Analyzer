from __future__ import annotations

import streamlit as st

from ..services import RiskPolicy
from .charts import render_price_chart
from .components import callout, kpi_grid, page_header, section_header
from .context import AppContext
from .pages import render_backtest, render_dashboard, render_model_health, render_trading
from .sidebar import render_settings_form, save_settings
from .tables import orders_table, positions_table, signal_table


def _analysis(ctx: AppContext):
    with st.spinner("Evaluating watchlist…"):
        result = ctx.analyze_watchlist()
    if not result.available:
        st.error("No watchlist symbol returned usable data. Review symbols and history/interval settings.")
        for symbol, error in result.unavailable.items(): st.caption(f"{symbol}: {error}")
        st.stop()
    for symbol, error in result.unavailable.items(): st.warning(f"{symbol} was skipped: {error}")
    return result


def _prices(result) -> dict[str, float]:
    return {symbol: state.price for symbol, state in result.available.items()}


def dashboard_page(ctx: AppContext) -> None:
    result = _analysis(ctx); prices = _prices(result); summary = ctx.portfolio.summary(prices)
    primary_symbol = next(iter(result.available)); primary = result.available[primary_symbol]
    page_header("Dashboard", "Portfolio, market signals, model health, and recent paper execution in one operating view.", meta=f"Data as of {primary.timestamp}")
    kpi_grid([
        {"label":"Portfolio value","value":f"${summary['equity']:,.2f}","delta":f"{summary['return_pct']:+.2f}% since reset","tone":"positive" if summary['pnl'] >= 0 else "negative","icon":"$"},
        {"label":"Paper P&L","value":f"${summary['pnl']:,.2f}","delta":f"Cash ${summary['cash']:,.0f}","tone":"positive" if summary['pnl'] >= 0 else "negative","icon":"↗"},
        {"label":"Tracked markets","value":str(len(result.available)),"delta":f"{ctx.settings.interval} · {ctx.settings.period}","tone":"blue","icon":"◎"},
        {"label":"Reference signal","value":primary.signal.action.upper(),"delta":f"{primary_symbol} · {primary.signal.confidence:.0%} confidence","tone":"positive" if primary.signal.action == 'Buy' else "negative" if primary.signal.action == 'Sell' else "blue","icon":"◇"},
    ])
    render_dashboard(result.available, ctx.portfolio, prices)


def markets_page(ctx: AppContext) -> None:
    result = _analysis(ctx)
    page_header("Markets", "Inspect watchlist prices, model signals, cost-adjusted edge, and technical price action.", meta=f"{ctx.settings.interval} bars · horizon {ctx.settings.horizon}")
    section_header("Watchlist signal board", "Signals are research outputs, not trade instructions")
    st.dataframe(signal_table(result.available), width="stretch", hide_index=True)
    section_header("Market detail")
    symbol = st.selectbox("Market", list(result.available), key="markets_symbol"); state = result.available[symbol]
    metrics = st.columns(4); metrics[0].metric("Last price", f"${state.price:,.2f}"); metrics[1].metric("Model signal", state.signal.action); metrics[2].metric("Predicted return", f"{state.predicted_return*100:+.3f}%"); metrics[3].metric("Confidence", f"{state.signal.confidence:.0%}")
    render_price_chart(state.bars, symbol); st.caption(f"Latest observation: {state.timestamp}. The chart and prediction use historical market data and simulated assumptions.")


def ai_trader_page(ctx: AppContext) -> None:
    page_header("AI Trader", "Autonomous strategy evaluation and paper-only execution workspace.", eyebrow="PAPER AUTOMATION")
    callout("Phase status", "The dedicated AI Trader page is wired into application navigation. Autonomous decision, sizing, risk, and journal services are implemented in the next approved engineering phases on this branch.")


def portfolio_page(ctx: AppContext) -> None:
    result = _analysis(ctx); prices = _prices(result); summary = ctx.portfolio.summary(prices)
    page_header("Portfolio", "Paper account equity, cash, open positions, and realized/unrealized performance.", eyebrow="PAPER PORTFOLIO")
    kpi_grid([
        {"label":"Equity","value":f"${summary['equity']:,.2f}","delta":f"{summary['return_pct']:+.2f}% total return","tone":"positive" if summary['pnl'] >= 0 else "negative","icon":"$"},
        {"label":"Cash","value":f"${summary['cash']:,.2f}","delta":"Available paper cash","tone":"blue","icon":"▣"},
        {"label":"Total P&L","value":f"${summary['pnl']:,.2f}","delta":"Since portfolio initialization","tone":"positive" if summary['pnl'] >= 0 else "negative","icon":"↗"},
        {"label":"Open positions","value":str(sum(1 for p in ctx.portfolio.positions.values() if p.quantity > 0)),"delta":"Long-only paper inventory","tone":"blue","icon":"◫"},
    ])
    section_header("Open positions"); frame = positions_table(ctx.portfolio, prices)
    if frame.empty: st.info("No open paper positions.")
    else: st.dataframe(frame, width="stretch", hide_index=True)
    section_header("Manual paper execution"); render_trading(result.available, ctx.portfolio, ctx.portfolio_service, ctx.store, prices)


def trade_journal_page(ctx: AppContext) -> None:
    page_header("Trade Journal", "Chronological audit trail for paper orders and strategy-driven execution events.", eyebrow="EXECUTION AUDIT")
    frame = orders_table(ctx.store.orders())
    if frame.empty: st.info("No paper trades have been recorded yet."); return
    buys = int((frame["Side"].str.lower() == "buy").sum()) if "Side" in frame else 0; sells = int((frame["Side"].str.lower() == "sell").sum()) if "Side" in frame else 0
    kpi_grid([{"label":"Recorded orders","value":str(len(frame)),"delta":"Persistent SQLite audit rows","tone":"blue","icon":"≡"},{"label":"Buy fills","value":str(buys),"delta":"Paper entries","tone":"positive","icon":"↑"},{"label":"Sell fills","value":str(sells),"delta":"Paper exits","tone":"negative","icon":"↓"}], columns=3)
    section_header("Execution history"); st.dataframe(frame, width="stretch", hide_index=True)


def model_analytics_page(ctx: AppContext) -> None:
    result = _analysis(ctx); page_header("Model Analytics", "Holdout diagnostics, purged walk-forward validation, benchmark ladder, and complexity evidence gate.", eyebrow="MODEL GOVERNANCE"); render_model_health(result.available, ctx.analysis_service)


def backtesting_page(ctx: AppContext) -> None:
    result = _analysis(ctx); page_header("Backtesting", "Leakage-aware purged holdout simulation with next-bar execution and transaction-cost assumptions.", eyebrow="STRATEGY RESEARCH"); render_backtest(result.available, ctx.analysis_service, ctx.request, ctx.settings.starting_cash)


def risk_analytics_page(ctx: AppContext) -> None:
    result = _analysis(ctx); prices = _prices(result); summary = ctx.portfolio.summary(prices); positions = positions_table(ctx.portfolio, prices)
    page_header("Risk Analytics", "Monitor portfolio exposure and the protective rules applied to the paper account.", eyebrow="RISK CONTROL")
    invested = max(summary["equity"] - summary["cash"], 0.0); exposure = invested / summary["equity"] * 100 if summary["equity"] else 0.0
    kpi_grid([{"label":"Portfolio exposure","value":f"{exposure:.1f}%","delta":f"${invested:,.0f} marked value","tone":"warning" if exposure > 70 else "blue","icon":"◔"},{"label":"Stop loss","value":f"{ctx.settings.stop_loss_pct:.1f}%","delta":"Automated exit threshold" if ctx.settings.automation_enabled else "Exit automation disabled","tone":"warning","icon":"↓"},{"label":"Take profit","value":f"{ctx.settings.take_profit_pct:.1f}%","delta":"Automated exit threshold" if ctx.settings.automation_enabled else "Exit automation disabled","tone":"positive","icon":"↑"},{"label":"Open positions","value":str(len(positions)),"delta":"Current paper positions","tone":"blue","icon":"◫"}])
    policy = RiskPolicy(ctx.settings.automation_enabled, ctx.settings.stop_loss_pct, ctx.settings.take_profit_pct); section_header("Protective automation")
    if policy.enabled: st.success("Stop-loss and take-profit checks are active for open paper positions on each application refresh.")
    else: st.info("Protective exits are disabled. Enable them from Settings when testing automated position management.")
    if not positions.empty: section_header("Position risk table"); st.dataframe(positions, width="stretch", hide_index=True)


def settings_page(ctx: AppContext) -> None:
    page_header("Settings", "Configure watchlist, data horizon, model thresholds, paper capital, trading costs, and protective exits.", eyebrow="APPLICATION CONTROL")
    if ctx.portfolio_reset: st.info("Paper portfolio was reset because capital or transaction-cost assumptions changed.")
    with st.form("settings_form"):
        updated = render_settings_form(ctx.settings); submitted = st.form_submit_button("Save application settings", type="primary", use_container_width=True)
    if submitted: save_settings(updated); st.success("Settings saved. Pages will use the updated configuration."); st.rerun()
    st.warning("Changing starting cash, commission, or slippage resets the in-memory paper portfolio. Historical SQLite journal rows are retained.")
