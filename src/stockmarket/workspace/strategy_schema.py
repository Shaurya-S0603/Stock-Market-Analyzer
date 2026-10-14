"""Strict JSON-only strategy definitions. No custom Python or eval execution."""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RuleType = Literal[
    "sma_cross", "ema_cross", "rsi_threshold", "macd_cross",
    "price_above_sma", "price_below_sma", "breakout_high", "breakout_low",
    "volume_above_average",
]


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: RuleType
    fast_period: int = Field(default=20, ge=2, le=250)
    slow_period: int = Field(default=50, ge=2, le=250)
    period: int = Field(default=14, ge=2, le=250)
    direction: Literal["above", "below"] = "above"
    threshold: float = Field(default=50, ge=0, le=100)
    volume_multiplier: float = Field(default=1.5, gt=0, le=100)

    @model_validator(mode="after")
    def check(self):
        if self.type in {"sma_cross", "ema_cross"} and self.fast_period >= self.slow_period:
            raise ValueError("Fast moving-average period must be smaller than slow")
        if self.type in {"breakout_high", "breakout_low"} and self.period < 2:
            raise ValueError("Breakout period must be at least 2")
        return self


class RuleGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operator: Literal["all", "any"] = "all"
    rules: list[Rule] = Field(min_length=1, max_length=8)


class Risk(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    sizing: Literal["percent_of_equity", "fixed_cash", "fixed_quantity"] = "percent_of_equity"
    value: float = Field(default=10.0, gt=0, le=1_000_000)
    max_exposure_pct: float = Field(default=100, gt=0, le=100)
    stop_loss_pct: float | None = Field(default=7.0, gt=0, le=99)
    take_profit_pct: float | None = Field(default=20.0, gt=0, le=1000)
    trailing_stop_pct: float | None = Field(default=None, gt=0, le=99)
    max_holding_bars: int | None = Field(default=None, ge=1, le=10000)

    @model_validator(mode="after")
    def check(self):
        if self.sizing == "percent_of_equity" and self.value > 100:
            raise ValueError("Percentage-of-equity sizing cannot exceed 100%")
        if self.sizing == "fixed_quantity" and not self.value.is_integer():
            raise ValueError("Fixed-share quantity must be an integer")
        return self


class Costs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    commission_fixed: float = Field(default=0.0, ge=0, le=1000)
    commission_pct: float = Field(default=0.0, ge=0, le=10)
    slippage_pct: float = Field(default=0.05, ge=0, le=10)


class Strategy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    symbol: str = Field(default="MSFT", min_length=1, max_length=40)
    timeframe: Literal["1d", "1h", "5m", "15m", "1wk", "1mo"] = "1d"
    entry: RuleGroup
    exit: RuleGroup
    risk: Risk = Field(default_factory=Risk)
    costs: Costs = Field(default_factory=Costs)

    @model_validator(mode="after")
    def check(self):
        from .database import clean_symbol
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Strategy name cannot be empty")
        self.symbol = clean_symbol(self.symbol)
        return self


def parse_strategy(value: str | dict | Strategy) -> Strategy:
    if isinstance(value, Strategy):
        return value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise ValueError("Strategy must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("Strategy must be a JSON object")
    return Strategy.model_validate(value)


def example_strategy() -> Strategy:
    return Strategy(
        name="SMA trend with RSI filter", symbol="MSFT",
        entry=RuleGroup(operator="all", rules=[
            Rule(type="sma_cross", fast_period=10, slow_period=30, direction="above"),
            Rule(type="rsi_threshold", direction="below", threshold=75),
        ]),
        exit=RuleGroup(operator="any", rules=[
            Rule(type="sma_cross", fast_period=10, slow_period=30, direction="below"),
            Rule(type="rsi_threshold", direction="above", threshold=80),
        ]),
    )
