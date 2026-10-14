import json

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from stockmarket.workspace.strategy_schema import Strategy, Rule, RuleGroup, parse_strategy, example_strategy
from stockmarket.workspace.strategy_signals import evaluate_strategy, evaluate_rule


def sample(n=100):
    close = 50 + np.arange(n) * .5 + np.sin(np.arange(n)) * 2
    return pd.DataFrame({
        "open": close - .2, "high": close + 1, "low": close - 1,
        "close": close, "volume": np.full(n, 1000),
    }, index=pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC"))


def test_json_schema_round_trip_and_unknown_code_rejected():
    template = example_strategy()
    assert parse_strategy(template.model_dump_json()) == template
    assert parse_strategy(template.model_dump()) == template
    raw = template.model_dump()
    raw["python"] = "exec('malicious')"
    with pytest.raises(ValidationError, match="Extra inputs"):
        parse_strategy(raw)
    with pytest.raises(ValueError, match="JSON"):
        parse_strategy("{garbled")


def test_invalid_numeric_ranges_and_rule_types_rejected():
    with pytest.raises(ValidationError):
        Rule(type="shell_command")
    with pytest.raises(ValidationError):
        Rule(type="sma_cross", fast_period=50, slow_period=20)
    with pytest.raises(ValidationError):
        example_strategy().model_copy(update={"risk": {"sizing":"percent_of_equity","value":101}})
    config = example_strategy().model_dump()
    config["risk"]["value"] = -1
    with pytest.raises(ValidationError):
        parse_strategy(config)


def test_signal_calculation_is_causal_and_has_warmup():
    original = sample(120)
    strategy = example_strategy()
    prefix = evaluate_strategy(original.iloc[:85], strategy)
    full = evaluate_strategy(original, strategy)
    pd.testing.assert_frame_equal(prefix, full.iloc[:85])
    assert not prefix.iloc[0]["entry"]
    assert not prefix.iloc[0]["exit"]


def test_crossover_requires_prior_bar_not_just_persistent_above():
    frame = sample()
    crossover = Rule(type="sma_cross", fast_period=4, slow_period=12, direction="above")
    signal = evaluate_rule(frame, crossover)
    assert not signal.iloc[:12].any()
    assert signal.sum() <= 10
    buy_state = evaluate_rule(frame, Rule(type="price_above_sma", period=10))
    assert buy_state.iloc[-1]
