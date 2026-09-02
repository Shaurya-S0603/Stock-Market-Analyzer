from __future__ import annotations

import pandas as pd
import streamlit as st

from ..services import (
    ExperimentRegistry,
    assess_champion_challenger,
    run_monte_carlo_stress_test,
    run_portfolio_walk_forward,
)
from .components import callout, kpi_grid, page_header, section_header
from .context import AppContext


def _watchlist(ctx: AppContext):
    with st.spinner("Building v1 research snapshot…"):
        result = ctx.analyze_watchlist()
    if not result.available:
        st.error("No configured symbol returned enough data for the research lab.")
        for symbol, error in result.unavailable.items():
            st.caption(f"{symbol}: {error}")
        st.stop()
    return result


def _allocations(ctx: AppContext) -> dict[str, float]:
    profile = ctx.store.portfolio_profile() or {}
    return {str(symbol).upper(): float(weight) for symbol, weight in profile.get("allocations", {}).items()}


def _governance_tab(ctx: AppContext, result) -> None:
    section_header("Champion vs challenger", "Challengers must improve error without sacrificing direction or strategy evidence")
    symbol = st.selectbox("Governance symbol", sorted(result.available), key="v1_governance_symbol")
    analysis = result.available[symbol]
    try:
        rows, _ = ctx.analysis_service.ensemble_benchmark_report(analysis)
        decision = assess_champion_challenger(rows)
    except ValueError as exc:
        st.info(f"Governance comparison unavailable: {exc}")
        return

    kpi_grid([
        {
            "label": "Recommendation",
            "value": decision.recommendation.replace("_", " "),
            "delta": f"Champion · {decision.champion}",
            "tone": "positive" if decision.recommendation == "PROMOTE_CHALLENGER" else "blue",
            "icon": "◎",
        },
        {
            "label": "Best challenger",
            "value": decision.challenger,
            "delta": f"RMSE {decision.rmse_improvement:+.1%}",
            "tone": "positive" if decision.rmse_improvement > 0 else "warning",
            "icon": "Δ",
        },
        {
            "label": "Direction delta",
            "value": f"{decision.directional_delta:+.1%}",
            "delta": "Challenger minus champion",
            "tone": "positive" if decision.directional_delta >= 0 else "warning",
            "icon": "↗",
        },
        {
            "label": "Strategy-return delta",
            "value": f"{decision.strategy_return_delta:+.4f}",
            "delta": "Mean purged-fold difference",
            "tone": "positive" if decision.strategy_return_delta > 0 else "warning",
            "icon": "$",
        },
    ])
    frame = pd.DataFrame(rows).sort_values(["rmse", "complexity_rank"])
    st.dataframe(
        frame,
        width="stretch",
        hide_index=True,
        column_config={
            "rmse": st.column_config.NumberColumn(format="%.6f"),
            "mae": st.column_config.NumberColumn(format="%.6f"),
            "directional_accuracy": st.column_config.NumberColumn(format="%.1%"),
            "strategy_return": st.column_config.NumberColumn(format="%+.5f"),
        },
    )
    callout("Promotion boundary", decision.reason)
    st.caption("A PROMOTE recommendation is research evidence only. v1.0 does not silently swap the production model used by PAPER AUTO.")


def _stress_tab(ctx: AppContext, result) -> None:
    section_header("Monte Carlo stress test", "Block-bootstrap the leakage-safe holdout equity curve to estimate outcome dispersion")
    symbol = st.selectbox("Stress-test symbol", sorted(result.available), key="v1_stress_symbol")
    simulations = st.slider("Simulations", 500, 5000, 1500, 500, key="v1_mc_simulations")
    block_size = st.slider("Bootstrap block size", 2, 20, 5, 1, key="v1_mc_block_size")
    if not st.button("Run Monte Carlo stress test", type="primary", use_container_width=True, key="run_v1_mc"):
        st.info("Run the stress test to estimate the distribution of strategy returns and drawdowns from the current holdout behavior.")
        return
    try:
        report = ctx.analysis_service.backtest(result.available[symbol], ctx.request, ctx.settings.starting_cash)
        stress = run_monte_carlo_stress_test(
            report["equity_curve"],
            simulations=int(simulations),
            block_size=int(block_size),
        )
    except ValueError as exc:
        st.info(f"Stress test unavailable: {exc}")
        return
    st.session_state.v1_last_monte_carlo = stress.__dict__
    kpi_grid([
        {"label":"Median return","value":f"{stress.median_return_pct:+.2f}%","delta":f"{stress.simulations:,} simulations","tone":"positive" if stress.median_return_pct >= 0 else "negative","icon":"◎"},
        {"label":"5% return tail","value":f"{stress.p05_return_pct:+.2f}%","delta":f"95% tail {stress.p95_return_pct:+.2f}%","tone":"warning","icon":"↓"},
        {"label":"Probability of loss","value":f"{stress.probability_of_loss:.1%}","delta":"Bootstrap estimate, not a forecast","tone":"warning" if stress.probability_of_loss > .35 else "blue","icon":"!"},
        {"label":"Severe drawdown tail","value":f"{stress.p95_max_drawdown_pct:.2f}%","delta":f"Median DD {stress.median_max_drawdown_pct:.2f}%","tone":"warning","icon":"↘"},
    ])
    callout("Interpretation", "Monte Carlo results resample historical strategy returns in short blocks. They quantify sensitivity to return ordering and clustering; they do not guarantee future outcomes.")


def _portfolio_validation_tab(ctx: AppContext, result) -> None:
    section_header("Portfolio walk-forward", "Validate the configured symbols together with sleeves, costs, exposure limits, and correlation controls")
    allocations = _allocations(ctx)
    if not allocations:
        st.info("No persistent portfolio allocation profile is available.")
        return
    st.dataframe(
        pd.DataFrame([{"Symbol": symbol, "Allocation %": weight} for symbol, weight in allocations.items()]),
        width="stretch",
        hide_index=True,
    )
    if not st.button("Run portfolio walk-forward", type="primary", use_container_width=True, key="run_v1_portfolio_wf"):
        st.info("Run the portfolio validation to evaluate the combined allocation/risk system across purged expanding folds.")
        return
    try:
        report = run_portfolio_walk_forward(
            result.available,
            allocations,
            starting_cash=ctx.settings.starting_cash,
            commission_rate=ctx.settings.commission_rate,
            slippage_rate=ctx.settings.slippage_rate,
            buy_threshold=ctx.settings.buy_threshold,
            sell_threshold=ctx.settings.sell_threshold,
        )
    except ValueError as exc:
        st.info(f"Portfolio walk-forward unavailable: {exc}")
        return
    st.session_state.v1_last_portfolio_walk_forward = {
        "summary": {
            "mean_strategy_return_pct": report.mean_strategy_return_pct,
            "mean_benchmark_return_pct": report.mean_benchmark_return_pct,
            "mean_excess_return_pct": report.mean_excess_return_pct,
            "worst_drawdown_pct": report.worst_drawdown_pct,
            "total_trades": report.total_trades,
        },
        "folds": [row.__dict__ for row in report.folds],
    }
    kpi_grid([
        {"label":"Mean strategy return","value":f"{report.mean_strategy_return_pct:+.2f}%","delta":f"Benchmark {report.mean_benchmark_return_pct:+.2f}%","tone":"positive" if report.mean_strategy_return_pct >= 0 else "negative","icon":"↗"},
        {"label":"Mean excess return","value":f"{report.mean_excess_return_pct:+.2f}%","delta":f"{len(report.folds)} purged folds","tone":"positive" if report.mean_excess_return_pct >= 0 else "warning","icon":"Δ"},
        {"label":"Worst drawdown","value":f"{report.worst_drawdown_pct:.2f}%","delta":"Across portfolio folds","tone":"warning","icon":"↓"},
        {"label":"Simulated executions","value":str(report.total_trades),"delta":"All folds combined","tone":"blue","icon":"#"},
    ])
    st.dataframe(pd.DataFrame([row.__dict__ for row in report.folds]), width="stretch", hide_index=True)


def _registry_tab(ctx: AppContext) -> None:
    section_header("Experiment registry", "Reproducible model identities, training signatures, validation metrics, and drift events")
    registry = ExperimentRegistry(ctx.store.path)
    experiments = registry.recent(limit=200)
    drift = registry.drift_events(limit=200)
    e_count = len(experiments)
    drift_count = len([row for row in drift if str(row.get("status", "")).upper() not in {"STABLE", "OK"}])
    symbols = len({row.get("symbol") for row in experiments}) if experiments else 0
    latest_status = str(drift[0].get("status", "NO DATA")) if drift else "NO DATA"
    kpi_grid([
        {"label":"Registered experiments","value":str(e_count),"delta":f"{symbols} symbols","tone":"blue","icon":"#"},
        {"label":"Drift events","value":str(len(drift)),"delta":f"{drift_count} non-stable","tone":"warning" if drift_count else "positive","icon":"≈"},
        {"label":"Latest drift status","value":latest_status,"delta":"Most recent recorded event","tone":"warning" if latest_status not in {"STABLE", "OK", "NO DATA"} else "blue","icon":"◎"},
        {"label":"Registry database","value":"ACTIVE","delta":str(ctx.store.path),"tone":"positive","icon":"DB"},
    ])
    experiments_tab, drift_tab = st.tabs(["Experiments", "Drift events"])
    with experiments_tab:
        if not experiments:
            st.info("No experiments have been registered yet. Run an AI Trader decision cycle to register current models.")
        else:
            frame = pd.DataFrame(experiments)
            keep = [column for column in ["created_at", "symbol", "model_name", "regime", "experiment_id", "model_hash"] if column in frame.columns]
            st.dataframe(frame[keep], width="stretch", hide_index=True)
    with drift_tab:
        if not drift:
            st.info("No drift comparisons have been recorded yet.")
        else:
            frame = pd.DataFrame(drift)
            st.dataframe(frame, width="stretch", hide_index=True)


def research_lab_page(ctx: AppContext) -> None:
    result = _watchlist(ctx)
    page_header(
        "Research Lab",
        "v1.0 model governance, strategy stress testing, portfolio-level validation, and experiment/drift audit in one research workspace.",
        eyebrow="QUANT RESEARCH",
        meta=f"{ctx.settings.period} · {ctx.settings.interval} · horizon {ctx.settings.horizon}",
    )
    governance, stress, portfolio, registry = st.tabs([
        "Champion / Challenger",
        "Monte Carlo",
        "Portfolio Walk-Forward",
        "Experiments & Drift",
    ])
    with governance:
        _governance_tab(ctx, result)
    with stress:
        _stress_tab(ctx, result)
    with portfolio:
        _portfolio_validation_tab(ctx, result)
    with registry:
        _registry_tab(ctx)
