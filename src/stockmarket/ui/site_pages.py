from __future__ import annotations

import pandas as pd
import streamlit as st

from ..services import (
    AITraderConfig,
    RiskLimits,
    RiskPolicy,
    TraderMode,
    build_allocation_snapshot,
    build_portfolio_attribution,
    build_rebalance_plan,
    build_symbol_strategy_stats,
    build_trader_analytics,
)
from .charts import render_decision_mix, render_portfolio_allocation, render_portfolio_history, render_price_chart, render_target_vs_actual_allocation
from .components import callout, kpi_grid, page_header, section_header
from .context import AppContext
from .onboarding import clear_portfolio_setup
from .pages import render_backtest, render_model_health, render_trading
from .portfolio_intelligence import rebalance_frame, render_attribution, render_symbol_stats
from .sidebar import render_settings_form, save_settings
from .tables import orders_table, positions_table, signal_table
from .trader import decisions_frame, load_trader_config, ranked_opportunities_frame, run_trader_cycle, save_trader_config


def _analysis(ctx: AppContext):
    with st.spinner("Evaluating watchlist…"):
        result = ctx.analyze_watchlist()
    if not result.available:
        st.error("No watchlist symbol returned usable data. Review symbols and history/interval settings.")
        for symbol, error in result.unavailable.items():
            st.caption(f"{symbol}: {error}")
        st.stop()
    for symbol, error in result.unavailable.items():
        st.warning(f"{symbol} was skipped: {error}")
    return result


def _prices(result) -> dict[str, float]:
    return {symbol: state.price for symbol, state in result.available.items()}


def _decision_frame_from_store(ctx: AppContext, limit: int = 100) -> pd.DataFrame:
    frame = pd.DataFrame(ctx.store.ai_decisions(limit=limit))
    if frame.empty:
        return frame
    frame["confidence"] = frame["confidence"].astype(float)
    frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce")
    return frame


def _allocation_rows(ctx: AppContext, prices: dict[str, float]):
    profile = ctx.store.portfolio_profile()
    if not profile:
        return []
    return build_allocation_snapshot(
        ctx.portfolio,
        prices,
        profile.get("allocations", {}),
        float(profile.get("cash_target_pct", 0.0)),
    )


def _allocation_frame(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame([row.__dict__ if hasattr(row, "__dict__") else row for row in rows])
    return frame.rename(columns={
        "symbol": "Symbol",
        "target_pct": "Target %",
        "actual_pct": "Actual %",
        "drift_pct": "Drift pp",
        "market_value": "Market value",
        "remaining_capacity": "Remaining capacity",
    })


def dashboard_page(ctx: AppContext) -> None:
    result = _analysis(ctx)
    prices = _prices(result)
    summary = ctx.portfolio.summary(prices)
    primary_symbol = next(iter(result.available))
    primary = result.available[primary_symbol]
    trader = build_trader_analytics(ctx.store)
    trader_config = load_trader_config()
    page_header("Dashboard", "Institutional-style operating view for market signals, paper portfolio performance, model confidence, and autonomous strategy activity.", meta=f"Market data · {primary.timestamp}")
    kpi_grid([
        {"label":"Portfolio value","value":f"${summary['equity']:,.2f}","delta":f"{summary['return_pct']:+.2f}% since reset","tone":"positive" if summary['pnl'] >= 0 else "negative","icon":"$"},
        {"label":"Paper P&L","value":f"${summary['pnl']:,.2f}","delta":f"Cash ${summary['cash']:,.0f}","tone":"positive" if summary['pnl'] >= 0 else "negative","icon":"↗"},
        {"label":"AI win rate","value":f"{trader.win_rate:.1%}","delta":f"{trader.closed_trades} closed AI trades","tone":"positive" if trader.win_rate >= .5 and trader.closed_trades else "blue","icon":"◎"},
        {"label":"AI Trader","value":trader_config.mode.value.replace("_", " "),"delta":f"{trader.executed_decisions} automated fills logged","tone":"positive" if trader_config.mode == TraderMode.PAPER_AUTO else "blue","icon":"AI"},
    ])

    section_header("Portfolio performance", "Snapshot history is recorded on AI Trader cycles")
    left, right = st.columns([1.7, 1])
    with left:
        with st.container(border=True):
            render_portfolio_history(ctx.store.portfolio_snapshots(limit=300))
    with right:
        with st.container(border=True):
            st.markdown("#### Strategy health")
            h = st.columns(2)
            h[0].metric("Realized AI P&L", f"${trader.realized_pnl:,.2f}")
            h[1].metric("Profit factor", f"{trader.profit_factor:.2f}")
            h[0].metric("Execution rate", f"{trader.execution_rate:.1%}")
            h[1].metric("Model gate pass", f"{trader.model_gate_pass_rate:.1%}")
            st.caption(f"Latest reference: {primary_symbol} · {primary.signal.action} · {primary.signal.confidence:.0%} confidence")

    allocation_rows = _allocation_rows(ctx, prices)
    section_header("Allocation discipline", "Configured portfolio sleeves versus current simulated exposure")
    alloc_left, alloc_right = st.columns([1.55, 1])
    with alloc_left:
        with st.container(border=True):
            render_target_vs_actual_allocation(allocation_rows)
    with alloc_right:
        frame = _allocation_frame(allocation_rows)
        if frame.empty:
            st.info("No persisted allocation profile.")
        else:
            st.dataframe(
                frame[["Symbol", "Target %", "Actual %", "Drift pp", "Remaining capacity"]],
                width="stretch",
                hide_index=True,
                column_config={
                    "Target %": st.column_config.NumberColumn(format="%.1f%%"),
                    "Actual %": st.column_config.NumberColumn(format="%.1f%%"),
                    "Drift pp": st.column_config.NumberColumn(format="%+.1f"),
                    "Remaining capacity": st.column_config.NumberColumn(format="$%.2f"),
                },
            )

    section_header("Market signal board", f"{ctx.settings.interval} bars · {ctx.settings.horizon}-bar forecast horizon")
    st.dataframe(signal_table(result.available), width="stretch", hide_index=True, column_config={
        "price": st.column_config.NumberColumn("Price", format="$%.2f"),
        "predicted_return_pct": st.column_config.NumberColumn("Predicted return", format="%.3f%%"),
        "net_edge_pct": st.column_config.NumberColumn("Net edge", format="%.3f%%"),
        "confidence": st.column_config.ProgressColumn("Confidence", min_value=0.0, max_value=1.0, format="%.0f%%"),
    })

    section_header("Recent AI decisions", "Accepted and rejected decisions remain visible for audit")
    recent = _decision_frame_from_store(ctx, 8)
    if recent.empty:
        st.info("No persisted AI Trader decisions yet. Run OBSERVE mode to validate decisions without executing paper orders.")
    else:
        st.dataframe(recent[["created_at","symbol","signal","decision","quantity","confidence","model_gate_passed","executed","reason"]], width="stretch", hide_index=True)


def markets_page(ctx: AppContext) -> None:
    result = _analysis(ctx)
    page_header("Markets", "Watchlist signal intelligence with current model edge, confidence, technical price structure, and transparent timestamps.", meta=f"{ctx.settings.interval} bars · horizon {ctx.settings.horizon}")
    section_header("Watchlist signal board", "Cost-adjusted model labels")
    st.dataframe(signal_table(result.available), width="stretch", hide_index=True)
    section_header("Market detail")
    symbol = st.selectbox("Market", list(result.available), key="markets_symbol")
    state = result.available[symbol]
    kpi_grid([
        {"label":"Last price","value":f"${state.price:,.2f}","delta":str(state.timestamp),"tone":"blue","icon":"$"},
        {"label":"Signal","value":state.signal.action.upper(),"delta":f"{state.signal.confidence:.0%} confidence","tone":"positive" if state.signal.action == "Buy" else "negative" if state.signal.action == "Sell" else "blue","icon":"◇"},
        {"label":"Forecast return","value":f"{state.predicted_return*100:+.3f}%","delta":f"{state.horizon} bars ahead","tone":"positive" if state.predicted_return >= 0 else "negative","icon":"↗"},
        {"label":"Net edge","value":f"{state.signal.net_edge*100:+.3f}%","delta":"After estimated round-trip costs","tone":"positive" if state.signal.net_edge >= 0 else "negative","icon":"≈"},
    ])
    with st.container(border=True):
        render_price_chart(state.bars, symbol)


def ai_trader_page(ctx: AppContext) -> None:
    config = load_trader_config()
    analytics = build_trader_analytics(ctx.store)
    page_header("AI Trader", "Autonomous signal evaluation, risk-aware sizing, transparent decision gates, and paper-only execution.", eyebrow="PAPER AUTOMATION", meta=f"Mode · {config.mode.value.replace('_', ' ')}")
    kpi_grid([
        {"label":"Trader mode","value":config.mode.value.replace("_", " "),"delta":"Simulation only","tone":"positive" if config.mode == TraderMode.PAPER_AUTO else "blue","icon":"AI"},
        {"label":"Win rate","value":f"{analytics.win_rate:.1%}","delta":f"{analytics.winning_trades} wins · {analytics.losing_trades} losses","tone":"positive" if analytics.win_rate >= .5 and analytics.closed_trades else "blue","icon":"◎"},
        {"label":"Realized AI P&L","value":f"${analytics.realized_pnl:,.2f}","delta":f"Expectancy ${analytics.expectancy:,.2f}","tone":"positive" if analytics.realized_pnl >= 0 else "negative","icon":"$"},
        {"label":"Profit factor","value":f"{analytics.profit_factor:.2f}","delta":f"{analytics.executed_decisions} executed decisions","tone":"positive" if analytics.profit_factor >= 1 else "warning","icon":"↗"},
    ])

    section_header("Trader controls", "OBSERVE records decisions without fills; PAPER AUTO uses simulated cash only")
    with st.form("ai_trader_config_form"):
        core = st.columns(3)
        modes = [item.value for item in TraderMode]
        mode = core[0].selectbox("Mode", modes, index=modes.index(config.mode.value), format_func=lambda value: value.replace("_", " ").title())
        min_confidence = core[1].slider("Minimum confidence", 0.0, 1.0, config.min_confidence, 0.05, format="%.0f%%")
        allocation_pct = core[2].slider("Target entry allocation (%)", 0.5, 25.0, config.allocation_pct, 0.5)
        with st.expander("Risk limits", expanded=True):
            limits = config.risk_limits
            r1 = st.columns(3)
            max_position_pct = r1[0].slider("Max position (%)", 1.0, 50.0, limits.max_position_pct, 1.0)
            max_exposure_pct = r1[1].slider("Max portfolio exposure (%)", 5.0, 100.0, limits.max_portfolio_exposure_pct, 5.0)
            max_positions = r1[2].number_input("Max open positions", 1, 25, limits.max_open_positions)
            r2 = st.columns(3)
            max_daily_trades = r2[0].number_input("Max daily trades", 1, 100, limits.max_daily_trades)
            max_daily_loss_pct = r2[1].slider("Max daily realized loss (%)", 0.5, 20.0, limits.max_daily_loss_pct, 0.5)
            volatility_target_pct = r2[2].slider("Volatility target (%)", 0.2, 5.0, limits.volatility_target_pct, 0.1)
        saved = st.form_submit_button("Save AI Trader configuration", type="primary", use_container_width=True)
    if saved:
        save_trader_config(AITraderConfig(
            TraderMode(mode), float(min_confidence), float(allocation_pct),
            RiskLimits(float(max_position_pct), float(max_exposure_pct), int(max_positions), int(max_daily_trades), float(max_daily_loss_pct), float(volatility_target_pct)),
        ))
        st.success("AI Trader configuration saved.")
        st.rerun()

    action = st.columns([1, 3])
    run_now = action[0].button("Run decision cycle", type="primary", use_container_width=True, disabled=config.mode == TraderMode.OFF)
    action[1].caption("Manual cycles run immediately. In PAPER AUTO, the app also checks every two minutes while this Streamlit session remains open and evaluates only when a new market-bar fingerprint appears.")
    if run_now:
        decisions = run_trader_cycle(ctx, config)
        executed = sum(1 for decision in decisions if decision.executed)
        st.success(f"Cycle evaluated {len(decisions)} symbols and executed {executed} paper fills.") if config.mode == TraderMode.PAPER_AUTO else st.info(f"Observed {len(decisions)} decisions with no paper fills.")

    section_header("Opportunity ranking", "Eligible BUY candidates are ordered by edge, confidence, and forecast quality before simulated sizing")
    ranking = ranked_opportunities_frame()
    if ranking.empty:
        st.info("Run a decision cycle to generate the current portfolio opportunity ranking.")
    else:
        st.dataframe(
            ranking,
            width="stretch",
            hide_index=True,
            column_config={
                "Confidence": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.0f%%"),
                "Predicted Return": st.column_config.NumberColumn(format="%+.4f"),
                "Net Edge": st.column_config.NumberColumn(format="%+.4f"),
                "Target Weight": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

    section_header("Latest decision cycle")
    frame = decisions_frame()
    if frame.empty:
        st.info("No session decision cycle yet. OBSERVE mode is the safest way to inspect behavior before enabling automated paper fills.")
    else:
        st.dataframe(frame, width="stretch", hide_index=True, column_config={"Price":st.column_config.NumberColumn(format="$%.2f"),"Confidence":st.column_config.ProgressColumn(min_value=0.0,max_value=1.0,format="%.0f%%")})

    history = ctx.store.ai_decisions(limit=250)
    section_header("Decision distribution", "Persistent audit history")
    with st.container(border=True):
        render_decision_mix(history)
    callout("Execution boundary", "PAPER AUTO can only submit simulated fills into PaperPortfolio. Automatic checks run only while this Streamlit session is open, are deduplicated by market-bar fingerprint, and have no brokerage authentication, funding, or real-order endpoint.")


def portfolio_page(ctx: AppContext) -> None:
    result = _analysis(ctx)
    prices = _prices(result)
    summary = ctx.portfolio.summary(prices)
    page_header("Portfolio", "Paper account equity, allocation, attribution, positions, and manual portfolio controls.", eyebrow="PAPER PORTFOLIO")
    positions = positions_table(ctx.portfolio, prices)
    kpi_grid([
        {"label":"Equity","value":f"${summary['equity']:,.2f}","delta":f"{summary['return_pct']:+.2f}% total return","tone":"positive" if summary['pnl'] >= 0 else "negative","icon":"$"},
        {"label":"Cash","value":f"${summary['cash']:,.2f}","delta":f"{summary['cash']/summary['equity']:.1%} of equity" if summary['equity'] else "","tone":"blue","icon":"▣"},
        {"label":"Total P&L","value":f"${summary['pnl']:,.2f}","delta":"Since portfolio initialization","tone":"positive" if summary['pnl'] >= 0 else "negative","icon":"↗"},
        {"label":"Open positions","value":str(len(positions)),"delta":"Long-only paper inventory","tone":"blue","icon":"◫"},
    ])
    profile = ctx.store.portfolio_profile() or {}
    allocation_rows = _allocation_rows(ctx, prices)
    section_header("Allocation control", "Target sleeves are ceilings; actual weights move with strategy decisions and market prices")
    a, b = st.columns([1.3, 1])
    with a:
        with st.container(border=True):
            render_target_vs_actual_allocation(allocation_rows)
    with b:
        with st.container(border=True):
            render_portfolio_allocation(ctx.portfolio, prices)
    allocation_frame = _allocation_frame(allocation_rows)
    if not allocation_frame.empty:
        st.dataframe(
            allocation_frame[["Symbol", "Target %", "Actual %", "Drift pp", "Market value", "Remaining capacity"]],
            width="stretch",
            hide_index=True,
            column_config={
                "Target %": st.column_config.NumberColumn(format="%.1f%%"),
                "Actual %": st.column_config.NumberColumn(format="%.1f%%"),
                "Drift pp": st.column_config.NumberColumn(format="%+.1f"),
                "Market value": st.column_config.NumberColumn(format="$%.2f"),
                "Remaining capacity": st.column_config.NumberColumn(format="$%.2f"),
            },
        )

    attribution = build_portfolio_attribution(ctx.store, ctx.portfolio, prices)
    section_header("Performance attribution", "Persistent realized outcomes plus current-session unrealized P&L, grouped by symbol")
    kpi_grid([
        {"label":"Persistent realized","value":f"${attribution.realized_pnl:,.2f}","delta":"Across stored paper orders","tone":"positive" if attribution.realized_pnl >= 0 else "negative","icon":"$"},
        {"label":"Current unrealized","value":f"${attribution.unrealized_pnl:,.2f}","delta":"Open in-memory positions","tone":"positive" if attribution.unrealized_pnl >= 0 else "negative","icon":"≈"},
        {"label":"Attributed total","value":f"${attribution.total_pnl:,.2f}","delta":f"{len(attribution.symbols)} symbols represented","tone":"positive" if attribution.total_pnl >= 0 else "negative","icon":"↗"},
        {"label":"Recorded fees","value":f"${attribution.fees:,.2f}","delta":f"{attribution.orders} stored orders","tone":"blue","icon":"#"},
    ])
    render_attribution(attribution)

    section_header("Open positions")
    if positions.empty:
        st.info("No open paper positions.")
    else:
        st.dataframe(positions, width="stretch", hide_index=True)

    with st.expander("Manual paper rebalance planner", expanded=False):
        callout(
            "Separate control path",
            "Rebalancing is manual and allocation-driven. It does not create model signals, alter opportunity rankings, or run inside PAPER AUTO.",
        )
        if not profile or not profile.get("allocations"):
            st.info("Create a portfolio allocation profile before using the rebalance planner.")
        else:
            tolerance = st.slider("Rebalance tolerance (percentage points)", 0.5, 10.0, 2.0, 0.5)
            plan = build_rebalance_plan(
                ctx.portfolio,
                prices,
                profile.get("allocations", {}),
                float(profile.get("cash_target_pct", 0.0)),
                tolerance_pct=float(tolerance),
            )
            plan_frame = rebalance_frame(plan)
            if plan_frame.empty:
                st.success("Current simulated allocation is within the selected tolerance or cannot be adjusted by whole shares.")
            else:
                st.dataframe(
                    plan_frame,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "Price": st.column_config.NumberColumn(format="$%.2f"),
                        "Estimated value": st.column_config.NumberColumn(format="$%.2f"),
                        "Current %": st.column_config.NumberColumn(format="%.1f%%"),
                        "Target %": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )
                st.caption(f"Estimated cash after plan: ${plan.estimated_cash_after:,.2f} · target cash value ${plan.target_cash_value:,.2f}. Transaction costs can make actual simulated fills differ slightly.")
                if st.button("Apply simulated rebalance", use_container_width=True, key="apply_rebalance"):
                    applied = 0
                    failures: list[str] = []
                    for instruction in plan.instructions:
                        try:
                            ctx.portfolio_service.execute(
                                instruction.symbol,
                                instruction.side,
                                instruction.quantity,
                                instruction.price,
                                reason="rebalance_manual",
                            )
                            applied += 1
                        except ValueError as exc:
                            failures.append(f"{instruction.symbol}: {exc}")
                    if failures:
                        st.warning("Some simulated rebalance instructions were skipped: " + "; ".join(failures))
                    if applied:
                        st.success(f"Applied {applied} simulated rebalance instruction(s).")
                        st.rerun()

    with st.expander("Manual paper execution", expanded=False):
        render_trading(result.available, ctx.portfolio, ctx.portfolio_service, ctx.store, prices)


def trade_journal_page(ctx: AppContext) -> None:
    analytics = build_trader_analytics(ctx.store)
    page_header("Trade Journal", "Persistent audit trail for autonomous decisions, rejected opportunities, simulated fills, and per-symbol strategy statistics.", eyebrow="EXECUTION AUDIT")
    kpi_grid([
        {"label":"AI decisions","value":str(analytics.decisions),"delta":f"{analytics.executed_decisions} executed","tone":"blue","icon":"≡"},
        {"label":"Rejected","value":str(analytics.rejected_decisions),"delta":"Failed evidence/risk gates","tone":"warning","icon":"×"},
        {"label":"Closed AI trades","value":str(analytics.closed_trades),"delta":f"{analytics.win_rate:.1%} win rate","tone":"positive" if analytics.win_rate >= .5 and analytics.closed_trades else "blue","icon":"◎"},
        {"label":"AI realized P&L","value":f"${analytics.realized_pnl:,.2f}","delta":f"PF {analytics.profit_factor:.2f}","tone":"positive" if analytics.realized_pnl >= 0 else "negative","icon":"$"},
    ])
    decisions_tab, orders_tab, cycles_tab, symbols_tab = st.tabs(["AI decisions", "Paper orders", "Decision cycles", "Symbol scorecard"])
    with decisions_tab:
        frame = _decision_frame_from_store(ctx, 500)
        if frame.empty: st.info("No AI decisions recorded.")
        else: st.dataframe(frame, width="stretch", hide_index=True)
    with orders_tab:
        frame = orders_table(ctx.store.orders())
        if frame.empty: st.info("No paper orders recorded.")
        else: st.dataframe(frame, width="stretch", hide_index=True)
    with cycles_tab:
        frame = pd.DataFrame(ctx.store.trader_runs(limit=250))
        if frame.empty: st.info("No AI Trader cycles recorded.")
        else: st.dataframe(frame, width="stretch", hide_index=True)
    with symbols_tab:
        render_symbol_stats(build_symbol_strategy_stats(ctx.store))


def model_analytics_page(ctx: AppContext) -> None:
    result = _analysis(ctx)
    page_header("Model Analytics", "Holdout diagnostics, purged walk-forward validation, benchmark ladder, and the evidence gate used by the AI Trader.", eyebrow="MODEL GOVERNANCE")
    render_model_health(result.available, ctx.analysis_service)


def backtesting_page(ctx: AppContext) -> None:
    result = _analysis(ctx)
    page_header("Backtesting", "Leakage-aware holdout simulation with next-bar execution, costs, benchmark comparison, and risk metrics.", eyebrow="STRATEGY RESEARCH")
    render_backtest(result.available, ctx.analysis_service, ctx.request, ctx.settings.starting_cash)


def risk_analytics_page(ctx: AppContext) -> None:
    result = _analysis(ctx)
    prices = _prices(result)
    summary = ctx.portfolio.summary(prices)
    positions = positions_table(ctx.portfolio, prices)
    config = load_trader_config()
    limits = config.risk_limits
    page_header("Risk Analytics", "Portfolio exposure, AI entry constraints, protective exits, and persisted risk events.", eyebrow="RISK CONTROL")
    invested = max(summary["equity"] - summary["cash"], 0.0)
    exposure = invested / summary["equity"] * 100 if summary["equity"] else 0.0
    kpi_grid([
        {"label":"Current exposure","value":f"{exposure:.1f}%","delta":f"Limit {limits.max_portfolio_exposure_pct:.0f}%","tone":"warning" if exposure > limits.max_portfolio_exposure_pct*.8 else "blue","icon":"◔"},
        {"label":"Max position","value":f"{limits.max_position_pct:.1f}%","delta":"Per entry cap before symbol sleeve","tone":"blue","icon":"▦"},
        {"label":"Daily loss stop","value":f"{limits.max_daily_loss_pct:.1f}%","delta":"Realized paper P&L limit","tone":"warning","icon":"↓"},
        {"label":"Max daily trades","value":str(limits.max_daily_trades),"delta":f"Max {limits.max_open_positions} open positions","tone":"blue","icon":"#"},
    ])
    policy = RiskPolicy(ctx.settings.automation_enabled, ctx.settings.stop_loss_pct, ctx.settings.take_profit_pct)
    section_header("Protective exits")
    st.success(f"Stop {policy.stop_loss_pct:.1f}% · Target {policy.take_profit_pct:.1f}% are active.") if policy.enabled else st.info("Stop-loss / take-profit automation is disabled in Settings.")
    allocation_frame = _allocation_frame(_allocation_rows(ctx, prices))
    if not allocation_frame.empty:
        section_header("Sleeve capacity", "User allocation ceilings operate in addition to global AI risk limits")
        st.dataframe(allocation_frame[["Symbol", "Target %", "Actual %", "Drift pp", "Remaining capacity"]], width="stretch", hide_index=True)
    if not positions.empty:
        section_header("Position exposure")
        st.dataframe(positions, width="stretch", hide_index=True)
    section_header("Risk event log")
    events = pd.DataFrame(ctx.store.risk_events(limit=100))
    if events.empty: st.info("No protective risk events recorded.")
    else: st.dataframe(events, width="stretch", hide_index=True)


def settings_page(ctx: AppContext) -> None:
    page_header("Settings", "Configure model/runtime assumptions separately from the persistent portfolio allocation profile.", eyebrow="APPLICATION CONTROL")
    if ctx.portfolio_reset:
        st.info("Paper portfolio was reset because transaction-cost assumptions changed.")
    with st.form("settings_form"):
        updated = render_settings_form(ctx.settings)
        submitted = st.form_submit_button("Save application settings", type="primary", use_container_width=True)
    if submitted:
        save_settings(updated)
        st.success("Settings saved. Pages will use the updated configuration.")
        st.rerun()

    section_header("Portfolio configuration", "Symbols, allocation ceilings, cash reserve, starting capital, and startup profile are managed together")
    profile = ctx.store.portfolio_profile()
    if not profile:
        st.info("No persisted portfolio profile is available.")
    else:
        p = st.columns(4)
        p[0].metric("Starting capital", f"${float(profile['starting_capital']):,.0f}")
        p[1].metric("Cash target", f"{float(profile['cash_target_pct']):.1f}%")
        p[2].metric("Risk profile", str(profile["risk_profile"]))
        p[3].metric("Startup mode", str(profile["trader_mode"]).replace("_", " "))
        st.dataframe(
            pd.DataFrame([
                {"Symbol": symbol, "Target ceiling %": weight}
                for symbol, weight in profile.get("allocations", {}).items()
            ]),
            width="stretch",
            hide_index=True,
        )
        if st.button("Reconfigure portfolio profile", use_container_width=True):
            clear_portfolio_setup()
            st.rerun()
    callout(
        "State behavior",
        "Reconfiguring the portfolio restarts onboarding and resets the in-memory PaperPortfolio, but persistent order, decision, model, and audit history is retained. Rebalancing remains a separate manual paper control on the Portfolio page.",
    )
