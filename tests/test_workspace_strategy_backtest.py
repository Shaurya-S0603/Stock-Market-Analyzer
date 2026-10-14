import numpy as np
import pandas as pd
import pytest

from stockmarket.workspace.strategy_schema import parse_strategy
from stockmarket.workspace.strategy_backtest import run_backtest, validate_backtest_bars


def bars(opens, closes=None, lows=None, highs=None):
    n = len(opens)
    closes = opens if closes is None else closes
    lows = [min(o, c)-.01 for o, c in zip(opens, closes)] if lows is None else lows
    highs = [max(o, c)+.01 for o, c in zip(opens, closes)] if highs is None else highs
    return pd.DataFrame({"open": opens, "high": highs, "low": lows,
                         "close": closes, "volume": [1000]*n},
                         index=pd.date_range("2026-01-01", periods=n, freq="d", tz="UTC"))


def strategy(*, entry=None, exit=None, risk=None, costs=None):
    return parse_strategy({
        "name": "Pure simulation", "symbol": "TEST", "timeframe": "1d",
        "entry": {"operator": "all", "rules": entry or [
            {"type":"rsi_threshold", "direction":"below", "threshold":100, "period":2}
        ]},
        "exit": {"operator": "all", "rules": exit or [
            {"type":"price_below_sma", "period":2}
        ]},
        "risk": {"value":50, "stop_loss_pct":None, "take_profit_pct":None,
                 **(risk or {})},
        "costs": {"commission_fixed":0, "commission_pct":0,
                  "slippage_pct":0, **(costs or {})},
    })


def test_fill_occurs_next_open_not_signal_close():
    frame = bars([10, 10, 10, 12, 12, 13], [10,10,10,10,13,13])
    result = run_backtest(frame, strategy(), starting_cash=1000)
    filled = [row for row in result["orders"] if row["status"] == "filled" and row["side"] == "buy"]
    assert filled
    assert filled[0]["timestamp"] == frame.index[3].isoformat()
    assert filled[0]["price"] == 12
    assert result["metrics"]["open_shares"] > 0


def test_commission_slippage_and_cash_reconciliation():
    frame = bars([10]*8, [10,10,10,10,10,10,10,10])
    # Monotone conditions give no RSI less-than-100 until enough history;
    # use a price-above-SMA after warm-up for a deterministic signal.
    conf = strategy(entry=[{"type":"price_above_sma", "period":2}], costs={"commission_fixed":2, "commission_pct":1, "slippage_pct":1})
    frame.loc[frame.index[3]:, "close"] = 11
    frame["high"] = frame[["open", "close"]].max(axis=1)+.1
    frame["low"] = frame[["open", "close"]].min(axis=1)-.1
    result = run_backtest(frame, conf, starting_cash=1000)
    buy = next(x for x in result["orders"] if x["side"] == "buy" and x["status"] == "filled")
    assert buy["price"] == pytest.approx(10.1)
    expected_fee = 2 + buy["quantity"]*10.1*.01
    assert buy["fee"] == pytest.approx(expected_fee)
    assert result["equity"][-1]["cash"] >= 0
    assert result["metrics"]["final_equity"] == pytest.approx(
        result["equity"][-1]["cash"] + result["equity"][-1]["market_value"], abs=1e-6
    )


def test_stop_first_when_both_stop_and_target_touched():
    frame = bars([100]*9)
    frame.loc[frame.index[3], "close"] = 102
    frame.loc[frame.index[3], "high"] = 103
    frame.loc[frame.index[3], "low"] = 99
    frame.loc[frame.index[4], ["open", "high", "low", "close"]] = [100,115,85,101]
    conf = strategy(entry=[{"type":"price_above_sma", "period":2}],
                    risk={"stop_loss_pct":5, "take_profit_pct":10})
    result = run_backtest(frame, conf, starting_cash=10000)
    trade = result["trades"][0]
    assert trade["reason"] == "stop_or_trailing_stop"
    assert trade["exit_price"] == pytest.approx(95)


def test_gap_through_stop_uses_open_price():
    frame = bars([100]*8)
    frame.loc[frame.index[3], ["high","close"]] = [103,102]
    # Entry fills on day 5 at 100; the adverse opening gap arrives on day 6.
    frame.loc[frame.index[5], ["open","high","low","close"]] = [80,90,75,82]
    conf = strategy(entry=[{"type":"price_above_sma", "period":2}],
                    exit=[{"type":"rsi_threshold", "direction":"above", "threshold":100, "period":2}],
                    risk={"stop_loss_pct":5, "take_profit_pct":10})
    result = run_backtest(frame, conf, starting_cash=10000)
    trade = result["trades"][0]
    assert trade["exit_price"] == pytest.approx(80)
    assert trade["reason"] == "stop_or_trailing_stop"


def test_unaffordable_trade_cannot_create_negative_cash():
    frame = bars([1000]*7)
    frame.loc[frame.index[3], ["high","close"]] = [1003,1002]
    conf = strategy(entry=[{"type":"price_above_sma", "period":2}],
                    risk={"sizing":"fixed_quantity", "value":1000})
    result = run_backtest(frame, conf, starting_cash=100)
    assert result["metrics"]["open_shares"] == 0
    assert result["metrics"]["final_equity"] == 100
    assert any(x["status"] == "rejected" for x in result["orders"])


def test_deterministic_output_and_future_data_does_not_change_old_signals():
    data = bars([100 + k for k in range(95)])
    conf = strategy(entry=[{"type":"price_above_sma","period":5}],
                    risk={"stop_loss_pct":None,"take_profit_pct":None})
    first = run_backtest(data, conf, starting_cash=1000)
    again = run_backtest(data, conf, starting_cash=1000)
    assert first == again
    shorter = run_backtest(data.iloc[:80], conf, starting_cash=1000)
    assert first["signals"][:80] == shorter["signals"]


def test_validation_rejects_garbled_price_and_mixed_adjustments():
    data = bars([100]*10)
    data.loc[data.index[3],"low"] = 105
    with pytest.raises(ValueError, match="Inconsistent"):
        validate_backtest_bars(data)
    data = bars([100]*10)
    data["adjustment_mode"] = ["raw"]*5 + ["adjusted"]*5
    with pytest.raises(ValueError, match="adjustment_mode"):
        validate_backtest_bars(data)
