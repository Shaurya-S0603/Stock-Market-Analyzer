"""Deterministic, long-only single-symbol bar-based backtester.

Signals evaluate a COMPLETED bar and fill no earlier than the next bar open.
On ambiguous intrabar stop/target collisions, the stop executes first.
Stops triggered across an adverse opening gap execute at that opening price.
Trailing stop highs are updated only after the current bar is finished.
This is simulation, never a brokerage execution interface.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math

import numpy as np
import pandas as pd

from .strategy_schema import Strategy, parse_strategy
from .strategy_signals import evaluate_strategy

BARS_PER_YEAR = {"1m": 98280, "5m": 19656, "15m": 6552, "1h": 1638,
                 "1d": 252, "1wk": 52, "1mo": 12}
REQUIRED = ["open", "high", "low", "close", "volume"]


def _round(value: float) -> float:
    return round(float(value), 8)


def _maybe(value: float) -> float | None:
    return _round(value) if math.isfinite(float(value)) else None


def _time(index_value) -> str:
    return pd.Timestamp(index_value).isoformat()


def validate_backtest_bars(data: pd.DataFrame, *, max_bars: int = 10000) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame) or len(data) < 3 or len(data) > max_bars:
        raise ValueError("Backtest requires 3–10,000 saved historical bars")
    if any(key not in data for key in REQUIRED):
        raise ValueError("Historical dataset lacks required OHLCV columns")
    if not isinstance(data.index, pd.DatetimeIndex) or data.index.tz is None:
        raise ValueError("Historical bars require timezone-aware timestamps")
    if data.index.has_duplicates or not data.index.is_monotonic_increasing:
        raise ValueError("Historical timestamps must be unique and chronological")
    numeric = data[REQUIRED].astype(float)
    if not np.isfinite(numeric.to_numpy()).all() or (numeric[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Invalid non-finite or nonpositive historical prices")
    if (numeric["volume"] < 0).any() or (numeric["high"] < numeric[["open", "low", "close"]].max(axis=1)).any() or (numeric["low"] > numeric[["open", "high", "close"]].min(axis=1)).any():
        raise ValueError("Inconsistent historical candles")
    for attr in ("provider", "adjustment_mode"):
        if attr in data and data[attr].dropna().nunique() > 1:
            raise ValueError(f"Backtest cannot combine different {attr} values")
    return data.copy()


def _execution_fee(quantity: int, price: float, fixed: float, rate_pct: float) -> float:
    return fixed + quantity * price * rate_pct / 100.0


def _performance(equity: pd.DataFrame, trades: list[dict], starting_cash: float,
                 bar_interval: str, periods_exposed: int, final_quantity: int) -> dict:
    values = equity["equity"].astype(float)
    returns = values.pct_change(fill_method=None).dropna()
    years = (equity.index[-1] - equity.index[0]).total_seconds() / (365.25*86400)
    end = float(values.iloc[-1])
    total = end / starting_cash - 1
    annualized = (end / starting_cash)**(1/years)-1 if years >= 30/365.25 and end > 0 else None
    bars_per_year = BARS_PER_YEAR[bar_interval]
    vol = float(returns.std(ddof=0)) if len(returns) > 1 else 0.0
    negative = returns.clip(upper=0)
    downside = float(np.sqrt(np.mean(np.square(negative)))) if len(negative) else 0.0
    sharpe = float(returns.mean() / vol * np.sqrt(bars_per_year)) if vol > 1e-12 else None
    sortino = float(returns.mean() / downside * np.sqrt(bars_per_year)) if downside > 1e-12 else None
    dd = values / values.cummax() - 1
    winners = [t["net_pnl"] for t in trades if t["net_pnl"] > 0]
    losers = [t["net_pnl"] for t in trades if t["net_pnl"] < 0]
    factor = sum(winners) / -sum(losers) if losers else None
    return {
        "starting_cash": _round(starting_cash), "final_equity": _round(end),
        "total_return_pct": _round(total*100),
        "cagr_pct": _maybe(annualized*100) if annualized is not None else None,
        "annualized_volatility_pct": _round(vol * np.sqrt(bars_per_year)*100),
        "sharpe": _maybe(sharpe) if sharpe is not None else None,
        "sortino": _maybe(sortino) if sortino is not None else None,
        "max_drawdown_pct": _round(dd.min()*100),
        "trade_count": len(trades),
        "win_rate_pct": _round(len(winners)/len(trades)*100) if trades else None,
        "profit_factor": _maybe(factor) if factor is not None else None,
        "average_win": _round(np.mean(winners)) if winners else None,
        "average_loss": _round(np.mean(losers)) if losers else None,
        "average_holding_bars": _round(np.mean([t["holding_bars"] for t in trades])) if trades else None,
        "exposure_pct": _round(periods_exposed / len(values)*100),
        "open_shares": final_quantity,
        "closed_net_pnl": _round(sum(t["net_pnl"] for t in trades)),
    }


def run_backtest(data: pd.DataFrame, strategy: Strategy | dict,
                 starting_cash: float = 10000.0, risk_free_rate: float = 0.0) -> dict:
    """Compute fills and portfolio accounting without touching paper positions."""
    definition = parse_strategy(strategy)
    frame = validate_backtest_bars(data)
    if not 0 < starting_cash <= 1e12 or not math.isfinite(starting_cash):
        raise ValueError("Starting simulated cash must be finite and positive")
    if risk_free_rate != 0:
        raise ValueError("Nonzero risk-free adjustment is not implemented; use zero for this phase")

    provider = str(frame["provider"].iloc[-1]) if "provider" in frame else "imported"
    adjustment = str(frame["adjustment_mode"].iloc[-1]) if "adjustment_mode" in frame else "unspecified"
    digest = sha256(frame[REQUIRED].to_csv(float_format="%.12g").encode("utf-8")).hexdigest()
    signals = evaluate_strategy(frame, definition)
    cash = float(starting_cash)
    qty, entry_price, entry_fee, entry_time, entry_idx = 0, 0.0, 0.0, None, None
    maximum_high = 0.0
    pending: str | None = None
    trades: list[dict] = []
    orders: list[dict] = []
    equity_records = []
    exposed = 0
    costs = definition.costs
    risk = definition.risk

    def exit_position(i: int, raw_price: float, reason: str) -> None:
        nonlocal cash, qty, entry_price, entry_fee, entry_time, entry_idx, maximum_high
        price = raw_price * (1 - costs.slippage_pct / 100)
        fee = _execution_fee(qty, price, costs.commission_fixed, costs.commission_pct)
        cash += qty * price - fee
        gross = qty * (price - entry_price)
        net = gross - entry_fee - fee
        trades.append({
            "symbol": definition.symbol, "entry_at": entry_time, "exit_at": _time(frame.index[i]),
            "entry_price": _round(entry_price), "exit_price": _round(price),
            "quantity": qty, "gross_pnl": _round(gross), "entry_fee": _round(entry_fee),
            "exit_fee": _round(fee), "net_pnl": _round(net),
            "return_pct": _round(net / (qty*entry_price + entry_fee)*100),
            "holding_bars": i - entry_idx, "reason": reason,
        })
        orders.append({"timestamp": _time(frame.index[i]), "side": "sell",
                       "quantity": qty, "price": _round(price), "fee": _round(fee),
                       "status": "filled", "reason": reason})
        qty, entry_price, entry_fee, entry_time, entry_idx, maximum_high = 0, 0.0, 0.0, None, None, 0.0

    for i, (timestamp, bar) in enumerate(frame.iterrows()):
        open_price = float(bar["open"])
        if pending == "exit" and qty:
            exit_position(i, open_price, "rule_exit")
        elif pending == "time" and qty:
            exit_position(i, open_price, "max_holding_period")
        elif pending == "entry" and qty == 0:
            purchase_price = open_price * (1 + costs.slippage_pct/100)
            equity_open = cash
            if risk.sizing == "fixed_quantity":
                requested = int(risk.value)
            else:
                requested_budget = (risk.value / 100 * equity_open if risk.sizing == "percent_of_equity" else risk.value)
                requested = int(max(0, math.floor(
                    (requested_budget - costs.commission_fixed) /
                    (purchase_price * (1 + costs.commission_pct / 100))
                )))
            hard_cap = min(cash, risk.max_exposure_pct / 100 * equity_open)
            affordable = int(max(0, math.floor(
                (hard_cap - costs.commission_fixed) /
                (purchase_price * (1 + costs.commission_pct / 100))
            )))
            number = min(requested, affordable)
            if number > 0:
                fee = _execution_fee(number, purchase_price, costs.commission_fixed, costs.commission_pct)
                cash -= number * purchase_price + fee
                if cash < -1e-7:
                    raise AssertionError("Backtest attempted to spend unavailable cash")
                cash = max(0.0, cash)
                qty, entry_price, entry_fee = number, purchase_price, fee
                entry_time, entry_idx = _time(timestamp), i
                maximum_high = purchase_price
                orders.append({"timestamp": _time(timestamp), "side": "buy",
                               "quantity": qty, "price": _round(purchase_price),
                               "fee": _round(fee), "status": "filled", "reason": "strategy_entry"})
            else:
                orders.append({"timestamp": _time(timestamp), "side": "buy", "quantity": 0,
                               "price": _round(purchase_price), "fee": 0,
                               "status": "rejected", "reason": "insufficient_cash_or_risk_capacity"})
        pending = None

        if qty:
            stop_candidates = []
            if risk.stop_loss_pct is not None:
                stop_candidates.append(entry_price * (1 - risk.stop_loss_pct / 100))
            if risk.trailing_stop_pct is not None:
                stop_candidates.append(maximum_high * (1 - risk.trailing_stop_pct / 100))
            stop_price = max(stop_candidates) if stop_candidates else None
            target_price = (entry_price * (1 + risk.take_profit_pct / 100)
                            if risk.take_profit_pct is not None else None)
            low, high = float(bar["low"]), float(bar["high"])
            # Stop has conservative priority if both extremes are reached.
            if stop_price is not None and low <= stop_price:
                exit_position(i, min(open_price, stop_price), "stop_or_trailing_stop")
            elif target_price is not None and high >= target_price:
                exit_position(i, max(open_price, target_price), "take_profit")
            else:
                maximum_high = max(maximum_high, high)

        market_value = qty * float(bar["close"])
        equity = cash + market_value
        if qty:
            exposed += 1
        equity_records.append({
            "timestamp": _time(timestamp), "cash": _round(cash),
            "market_value": _round(market_value), "equity": _round(equity),
            "quantity": qty, "drawdown_pct": 0.0,
        })
        if i < len(frame) - 1:
            if qty:
                if bool(signals["exit"].iloc[i]):
                    pending = "exit"
                elif risk.max_holding_bars is not None and i - entry_idx + 1 >= risk.max_holding_bars:
                    pending = "time"
            elif bool(signals["entry"].iloc[i]):
                pending = "entry"

    curve = pd.DataFrame(equity_records).set_index(pd.DatetimeIndex(frame.index))
    curve["drawdown_pct"] = (curve["equity"] / curve["equity"].cummax() - 1) * 100
    for i, val in enumerate(curve["drawdown_pct"].to_numpy()):
        equity_records[i]["drawdown_pct"] = _round(val)
    baseline_first_open = float(frame["open"].iloc[0])
    for i, bar in enumerate(frame.itertuples()):
        equity_records[i]["buy_hold_equity"] = _round(starting_cash *
                                                       (float(frame["close"].iloc[i]) / baseline_first_open))
    metrics = _performance(curve, trades, starting_cash, definition.timeframe, exposed, qty)
    metrics["buy_hold_return_pct"] = _round(
        (float(frame["close"].iloc[-1]) / baseline_first_open - 1)*100
    )
    return {
        "strategy_snapshot": definition.model_dump(mode="json"),
        "metadata": {
            "symbol": definition.symbol, "timeframe": definition.timeframe,
            "from": _time(frame.index[0]), "to": _time(frame.index[-1]),
            "provider": provider, "adjustment_mode": adjustment, "data_sha256": digest,
            "execution": "signal on completed close, fill next bar open; stop-first intrabar ambiguity",
            "benchmark": "fractional buy-and-hold first bar open, no benchmark commissions",
            "costs": costs.model_dump(mode="json"), "risk_free_rate": risk_free_rate,
            "bars": len(frame), "open_position_marked": qty > 0,
        },
        "metrics": metrics,
        "trades": trades,
        "orders": orders,
        "equity": equity_records,
        "signals": [
            {"timestamp": _time(frame.index[i]), "entry": bool(signals["entry"].iloc[i]),
             "exit": bool(signals["exit"].iloc[i])}
            for i in range(len(frame))
        ],
    }
