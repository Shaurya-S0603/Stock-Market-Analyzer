"""Streamlit visual rule editor, historical backtesting and saved-run comparison.

Research-only UI. Nothing here communicates with the paper account or brokerage.
"""
from __future__ import annotations

import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pydantic import ValidationError

from .strategy_backtest import run_backtest
from .strategy_repository import StrategyRepository, compare_results
from .strategy_schema import Rule, Strategy, example_strategy, parse_strategy
from .ui import workspace_db


RULES = {
    "sma_cross": "SMA crossover",
    "ema_cross": "EMA crossover",
    "rsi_threshold": "RSI threshold state",
    "macd_cross": "MACD crossover",
    "price_above_sma": "Price above SMA",
    "price_below_sma": "Price below SMA",
    "breakout_high": "Break above previous high",
    "breakout_low": "Break below previous low",
    "volume_above_average": "Volume greater than rolling average",
}


def _db():
    db = workspace_db(os.getenv("QUANTEDGE_WORKSPACE_DB", ".data/workspace.db"))
    return db, StrategyRepository(db)


def _strategy_options(repo: StrategyRepository) -> dict[str, dict]:
    return {f"{item['name']} (#{item['id']}, v{item['latest_version']})": item
            for item in repo.list_strategies()}


def _result_options(repo: StrategyRepository) -> dict[str, dict]:
    return {f"{item['name']} (#{item['id']})": item
            for item in repo.list_backtests()}


def _default_rule(name: str = "sma_cross") -> dict:
    return Rule(type=name).model_dump(mode="json")


def _rule_controls(prefix: str, number: int, drafts: list[dict]) -> list[dict]:
    assembled = []
    for n in range(number):
        old = drafts[n] if n < len(drafts) else _default_rule()
        st.caption(f"Condition {n+1}")
        col = st.columns([2.1, 1, 1, 1])
        name_choices = list(RULES)
        rule_type = col[0].selectbox("Rule", name_choices,
                                     index=name_choices.index(old.get("type", "sma_cross")),
                                     format_func=RULES.get, key=f"{prefix}_type_{n}")
        direction = col[1].selectbox("Direction", ["above", "below"],
                                     index=0 if old.get("direction", "above") == "above" else 1,
                                     key=f"{prefix}_direction_{n}")
        first = col[2].number_input("Fast/RSI period", min_value=2, max_value=250,
                                    value=int(old.get("fast_period", 20)), step=1,
                                    key=f"{prefix}_fast_{n}")
        second = col[3].number_input("Slow period", min_value=2, max_value=250,
                                     value=int(old.get("slow_period", 50)), step=1,
                                     key=f"{prefix}_slow_{n}")
        detail = st.columns(3)
        length = detail[0].number_input("Lookback", min_value=2, max_value=250,
                                        value=int(old.get("period", 14)), step=1,
                                        key=f"{prefix}_period_{n}")
        threshold = detail[1].number_input("RSI threshold", min_value=0.0, max_value=100.0,
                                           value=float(old.get("threshold", 50)), step=1.0,
                                           key=f"{prefix}_threshold_{n}")
        multiplier = detail[2].number_input("Volume multiplier", min_value=0.1,
                                            max_value=100.0, value=float(old.get("volume_multiplier", 1.5)),
                                            step=0.1, key=f"{prefix}_volume_{n}")
        assembled.append({
            "type": rule_type, "direction": direction, "fast_period": int(first),
            "slow_period": int(second), "period": int(length),
            "threshold": float(threshold), "volume_multiplier": float(multiplier),
        })
    return assembled


def _load_builder(strategy: dict, strategy_id: int | None = None) -> None:
    st.session_state["qe_builder_draft"] = strategy
    st.session_state["qe_builder_edit_id"] = strategy_id
    for k in list(st.session_state):
        if k.startswith(("qe_build_", "qe_entry_", "qe_exit_")):
            del st.session_state[k]


def strategy_builder_page() -> None:
    st.title("Visual Strategy Builder")
    st.caption("Validated, versioned JSON strategies. Signals use completed candles and are evaluated only in simulation.")
    db, repo = _db()
    options = _strategy_options(repo)
    if "qe_builder_draft" not in st.session_state:
        st.session_state["qe_builder_draft"] = example_strategy().model_dump(mode="json")
    selected = st.selectbox("Saved strategies", ["None"] + list(options), key="qe_builder_selected")
    row = st.columns(4)
    if row[0].button("Load saved", disabled=selected == "None"):
        item = options[selected]
        _load_builder(repo.load(item["id"])["definition"], item["id"])
        st.rerun()
    if row[1].button("New strategy"):
        _load_builder(example_strategy().model_dump(mode="json"))
        st.rerun()
    if row[2].button("Duplicate selected", disabled=selected == "None"):
        item = options[selected]
        copied = repo.load(item["id"])["definition"]
        copied["name"] += " Copy"
        _load_builder(copied)
        st.rerun()
    if row[3].button("Delete selected", disabled=selected == "None"):
        repo.delete(options[selected]["id"])
        _load_builder(example_strategy().model_dump(mode="json"))
        st.rerun()

    uploaded = st.file_uploader("Import validated strategy JSON", type=["json"])
    if st.button("Validate and load JSON", disabled=uploaded is None):
        try:
            parsed = parse_strategy(uploaded.getvalue().decode("utf-8"))
            _load_builder(parsed.model_dump(mode="json"))
            st.rerun()
        except (UnicodeDecodeError, ValueError, ValidationError) as exc:
            st.error(f"Invalid strategy: {exc}")

    draft = st.session_state["qe_builder_draft"]
    with st.form("qe_strategy_editor"):
        name = st.text_input("Strategy name", value=draft["name"], key="qe_build_name")
        description = st.text_area("Hypothesis/description", value=draft.get("description", ""), key="qe_build_desc")
        col = st.columns(2)
        symbol = col[0].text_input("Single market symbol", value=draft.get("symbol", "MSFT"), key="qe_build_symbol")
        intervals = ["1d", "1h", "5m", "15m", "1wk", "1mo"]
        interval = col[1].selectbox("Timeframe", intervals,
                                    index=intervals.index(draft.get("timeframe", "1d")), key="qe_build_interval")
        groups = {}
        for kind, heading in [("entry", "Entry conditions"), ("exit", "Exit conditions")]:
            st.subheader(heading)
            old_group = draft[kind]
            cols = st.columns(2)
            count = cols[0].number_input("Number of " + kind + " conditions", min_value=1, max_value=8,
                                         value=len(old_group["rules"]), step=1, key=f"qe_build_{kind}_count")
            operator = cols[1].selectbox("Combine " + kind + " conditions", ["all", "any"],
                                         index=0 if old_group["operator"] == "all" else 1,
                                         format_func=lambda x: "AND / all" if x == "all" else "OR / any",
                                         key=f"qe_build_{kind}_operator")
            groups[kind] = {"operator": operator, "rules": _rule_controls(
                f"qe_{kind}", int(count), old_group["rules"]
            )}
        st.subheader("Simulated risk and execution costs")
        prev = draft["risk"]
        cost = draft["costs"]
        cols = st.columns(3)
        sizing = cols[0].selectbox(
            "Sizing method", ["percent_of_equity", "fixed_cash", "fixed_quantity"],
            index=["percent_of_equity", "fixed_cash", "fixed_quantity"].index(prev["sizing"]),
            key="qe_build_sizing")
        value = cols[1].number_input("Entry size (%, cash, or shares)", min_value=.01,
                                     max_value=1_000_000., value=float(prev["value"]), key="qe_build_value")
        exposure = cols[2].number_input("Max exposure (%)", min_value=.1, max_value=100.,
                                        value=float(prev["max_exposure_pct"]), key="qe_build_exposure")
        stop = st.columns(4)
        use_stop = stop[0].checkbox("Stop loss", value=prev["stop_loss_pct"] is not None, key="qe_build_use_stop")
        stop_pct = stop[1].number_input("Stop loss (%)", min_value=.1, max_value=99.,
                                        value=float(prev["stop_loss_pct"] or 7), key="qe_build_stop")
        use_target = stop[2].checkbox("Take profit", value=prev["take_profit_pct"] is not None, key="qe_build_use_target")
        target_pct = stop[3].number_input("Take profit (%)", min_value=.1, max_value=1000.,
                                          value=float(prev["take_profit_pct"] or 20), key="qe_build_target")
        trailing = st.columns(4)
        use_trail = trailing[0].checkbox("Trailing stop", value=prev["trailing_stop_pct"] is not None,
                                         key="qe_build_use_trail")
        trail_pct = trailing[1].number_input("Trailing (%)", min_value=.1, max_value=99.,
                                             value=float(prev["trailing_stop_pct"] or 5), key="qe_build_trail")
        use_limit = trailing[2].checkbox("Max holding bars", value=prev["max_holding_bars"] is not None,
                                         key="qe_build_use_limit")
        bars_limit = trailing[3].number_input("Bars", min_value=1, max_value=10000,
                                              value=int(prev["max_holding_bars"] or 100), key="qe_build_limit")
        fees = st.columns(3)
        commission_fixed = fees[0].number_input("Flat commission", min_value=0., max_value=1000.,
                                                 value=float(cost["commission_fixed"]), key="qe_build_flat")
        commission_pct = fees[1].number_input("Commission (%)", min_value=0., max_value=10.,
                                               value=float(cost["commission_pct"]), key="qe_build_pct")
        slippage_pct = fees[2].number_input("Slippage (%)", min_value=0., max_value=10.,
                                             value=float(cost["slippage_pct"]), key="qe_build_slippage")
        action = st.columns(2)
        validate = action[0].form_submit_button("Validate & preview")
        save = action[1].form_submit_button("Save strategy/version")

    if validate or save:
        payload = {
            "name": name, "description": description, "symbol": symbol, "timeframe": interval,
            "entry": groups["entry"], "exit": groups["exit"],
            "risk": {
                "sizing": sizing, "value": float(value), "max_exposure_pct": float(exposure),
                "stop_loss_pct": float(stop_pct) if use_stop else None,
                "take_profit_pct": float(target_pct) if use_target else None,
                "trailing_stop_pct": float(trail_pct) if use_trail else None,
                "max_holding_bars": int(bars_limit) if use_limit else None,
            },
            "costs": {
                "commission_fixed": float(commission_fixed), "commission_pct": float(commission_pct),
                "slippage_pct": float(slippage_pct),
            },
        }
        try:
            checked = parse_strategy(payload)
            st.session_state["qe_builder_draft"] = checked.model_dump(mode="json")
            if save:
                saved = repo.save(checked, strategy_id=st.session_state.get("qe_builder_edit_id"))
                st.session_state["qe_builder_edit_id"] = saved["id"]
                st.success(f"Saved {saved['name']} version {saved['version']} in SQLite.")
            else:
                st.success("Strategy validated. No orders executed.")
            st.json(checked.model_dump(mode="json"))
        except (ValidationError, ValueError) as exc:
            st.error(str(exc))

    config = st.session_state["qe_builder_draft"]
    st.download_button("Export draft JSON", json.dumps(config, indent=2),
                       file_name="quantedge_strategy.json", mime="application/json")
    if st.session_state.get("qe_builder_edit_id"):
        history = repo.list_versions(st.session_state["qe_builder_edit_id"])
        st.caption("Saved versions: " + ", ".join(f"v{v}" for v in history))


def _results_view(result: dict) -> None:
    metrics = result["metrics"]
    st.subheader("Simulated performance")
    cols = st.columns(4)
    cols[0].metric("Total return", f"{metrics['total_return_pct']:+.2f}%")
    cols[1].metric("Max drawdown", f"{metrics['max_drawdown_pct']:.2f}%")
    cols[2].metric("Trades closed", str(metrics["trade_count"]))
    cols[3].metric("Buy & hold", f"{metrics['buy_hold_return_pct']:+.2f}%")
    st.dataframe([metrics], hide_index=True, use_container_width=True)
    frame = pd.DataFrame(result["equity"])
    if not frame.empty:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        curve = go.Figure()
        curve.add_trace(go.Scatter(x=frame["timestamp"], y=frame["equity"], name="Strategy equity"))
        curve.add_trace(go.Scatter(x=frame["timestamp"], y=frame["buy_hold_equity"], name="Buy & hold"))
        curve.update_layout(height=400, template="plotly_dark", hovermode="x unified")
        st.plotly_chart(curve, use_container_width=True)
        drawdown = go.Figure(go.Scatter(x=frame["timestamp"], y=frame["drawdown_pct"],
                                         fill="tozeroy", name="Drawdown (%)"))
        drawdown.update_layout(template="plotly_dark", height=250)
        st.plotly_chart(drawdown, use_container_width=True)
    trades = pd.DataFrame(result["trades"])
    st.subheader("Closed trades")
    if trades.empty:
        st.info("No closed trades. Open positions, if any, are marked at the last available close.")
    else:
        st.dataframe(trades, use_container_width=True, hide_index=True)
        st.download_button("Download trades CSV", trades.to_csv(index=False),
                           file_name="strategy_trades.csv", mime="text/csv")
    with st.expander("Execution audit and reproducibility"):
        st.json(result["metadata"])
        st.dataframe(result["orders"], hide_index=True, use_container_width=True)
        st.caption("Strategy is paper simulation only. Historical performance does not guarantee future outcomes.")


def strategy_backtesting_page() -> None:
    st.title("Rule-Based Backtesting Laboratory")
    st.caption("Separate from the legacy AI backtest. Signals on completed bars, simulated next-open fills only.")
    db, repo = _db()
    choices = _strategy_options(repo)
    if not choices:
        st.info("First create and save a strategy in Strategy Builder.")
        return
    pick = st.selectbox("Saved strategy", list(choices), key="qe_backtest_pick")
    item = choices[pick]
    definition = parse_strategy(repo.load(item["id"])["definition"])
    st.caption(f"{definition.symbol} · {definition.timeframe} · "
               "Uses locally cached historical bars; download data in Market Explorer/Charts first.")
    starting_cash = st.number_input("Starting simulated cash", min_value=100., max_value=1e10,
                                     value=10000., step=1000., key="qe_bt_starting_cash")
    exclude_last = st.checkbox("Exclude the most recent potentially unfinished bar", value=True)
    stored = db.load_candles(definition.symbol, definition.timeframe)
    if stored.empty:
        st.warning("No saved candles for this strategy symbol/timeframe. Fetch them in Market Explorer first.")
        return
    bounds = st.columns(2)
    start = bounds[0].date_input("Start", value=stored.index[0].date(),
                                 min_value=stored.index[0].date(), max_value=stored.index[-1].date())
    end = bounds[1].date_input("End", value=stored.index[-1].date(),
                               min_value=stored.index[0].date(), max_value=stored.index[-1].date())
    if st.button("Run reproducible backtest"):
        filtered = stored[(stored.index.date >= start) & (stored.index.date <= end)]
        if exclude_last:
            filtered = filtered.iloc[:-1]
        try:
            result = run_backtest(filtered, definition, starting_cash=float(starting_cash))
            st.session_state["qe_latest_strategy_backtest"] = result
            st.session_state["qe_latest_strategy_id"] = item["id"]
            st.session_state["qe_latest_strategy_version"] = item["latest_version"]
        except (ValueError, KeyError) as exc:
            st.error(str(exc))
    latest = st.session_state.get("qe_latest_strategy_backtest")
    if latest:
        _results_view(latest)
        report_name = st.text_input("Saved backtest label", value="Research trial")
        if st.button("Persist result in SQLite"):
            try:
                run_id = repo.save_backtest(
                    report_name, latest,
                    st.session_state.get("qe_latest_strategy_id"),
                    st.session_state.get("qe_latest_strategy_version"),
                )
                st.success(f"Saved complete backtest #{run_id}, including immutable configuration and equity history.")
            except ValueError as exc:
                st.error(str(exc))
    other = _result_options(repo)
    if other:
        selected = st.selectbox("Open an earlier saved backtest", ["None"] + list(other), key="qe_backtest_saved")
        if selected != "None":
            saved = repo.load_backtest(other[selected]["id"])
            st.caption(f"Stored at {saved['saved_at']}; no recalculation or provider request was made.")
            _results_view(saved["result"])


def backtest_comparison_page() -> None:
    st.title("Backtest Comparison")
    st.caption("Compares immutable saved runs; warns when periods, assets, fees or price bases differ.")
    _, repo = _db()
    candidates = _result_options(repo)
    selected = st.multiselect("Saved runs", list(candidates), key="qe_compare_selected")
    if not selected:
        st.info("Save at least one backtest, then select runs to compare.")
        return
    saved = [repo.load_backtest(candidates[name]["id"]) for name in selected]
    frame, warnings = compare_results(saved)
    for warning in warnings:
        st.warning(warning)
    st.dataframe(frame, use_container_width=True, hide_index=True)
    st.download_button("Export comparison CSV", data=frame.to_csv(index=False),
                       file_name="backtest_comparison.csv", mime="text/csv")
    fig = go.Figure()
    for run in saved:
        eq = pd.DataFrame(run["result"]["equity"])
        if eq.empty or float(eq["equity"].iloc[0]) <= 0:
            continue
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(eq["timestamp"], utc=True),
            y=eq["equity"] / eq["equity"].iloc[0] * 100,
            name=run["name"] + f" (#{run['id']})",
        ))
    fig.update_layout(
        title="Normalized equity (each saved run begins at index 100)",
        height=430, template="plotly_dark", hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
    if warnings:
        st.caption("Different assumptions mean the displayed curves are descriptive, not directly comparable.")
