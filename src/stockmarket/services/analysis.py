from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from ..backtest import run_backtest
from ..benchmarks import ModelGate, assess_model_gate, benchmark_models
from ..context_features import enrich_with_tactical_context
from ..features import build_features
from ..modeling import ModelResult, train_model
from ..multitimeframe import enrich_with_daily_context
from ..regime import regime_label
from ..signals import Signal, make_signal
from ..validation import walk_forward_scores


class MarketProvider(Protocol):
    def fetch(self, symbol: str, period: str, interval: str, minimum_rows: int = 80) -> pd.DataFrame: ...


@dataclass(frozen=True)
class AnalysisRequest:
    period: str
    interval: str
    horizon: int
    buy_threshold: float
    sell_threshold: float
    commission_rate: float
    slippage_rate: float
    context_period: str = "6mo"
    context_interval: str = "1d"
    benchmark_symbol: str = "SPY"

    @property
    def round_trip_cost(self) -> float:
        return 2.0 * (self.commission_rate + self.slippage_rate)

    @property
    def use_dual_timeframe(self) -> bool:
        return self.interval in {"1h", "60m"} and self.context_interval == "1d"


@dataclass
class SymbolAnalysis:
    symbol: str
    bars: pd.DataFrame
    training_features: pd.DataFrame
    live_features: pd.DataFrame
    model: ModelResult
    price: float
    timestamp: object
    predicted_return: float
    signal: Signal
    horizon: int
    context_bars: pd.DataFrame | None = None
    regime: str = "unknown"
    probability_profitable: float = 0.5


@dataclass
class WatchlistAnalysis:
    available: dict[str, SymbolAnalysis]
    unavailable: dict[str, str]


class AnalysisService:
    def __init__(self, provider: MarketProvider):
        self.provider = provider
        self._benchmark_cache: dict[tuple[str, str, str], pd.DataFrame | None] = {}

    def _benchmark_bars(self, request: AnalysisRequest) -> pd.DataFrame | None:
        key = (request.benchmark_symbol.upper(), request.period, request.interval)
        if key not in self._benchmark_cache:
            try:
                self._benchmark_cache[key] = self.provider.fetch(
                    request.benchmark_symbol,
                    request.period,
                    request.interval,
                    minimum_rows=80,
                )
            except (RuntimeError, ValueError):
                self._benchmark_cache[key] = None
        return self._benchmark_cache[key]

    def analyze_symbol(self, symbol: str, request: AnalysisRequest) -> SymbolAnalysis:
        bars = self.provider.fetch(symbol, request.period, request.interval)
        training_features = build_features(
            bars,
            horizon=request.horizon,
            include_target=True,
            round_trip_cost=request.round_trip_cost,
        )
        live_features = build_features(
            bars,
            horizon=request.horizon,
            include_target=False,
            round_trip_cost=request.round_trip_cost,
        )
        context_bars: pd.DataFrame | None = None
        current_regime = "tactical-only"

        if request.use_dual_timeframe:
            context_bars = self.provider.fetch(
                symbol,
                request.context_period,
                request.context_interval,
                minimum_rows=60,
            )
            training_features = enrich_with_daily_context(training_features, context_bars)
            live_features = enrich_with_daily_context(live_features, context_bars)
            current_regime = regime_label(live_features.iloc[-1])

        benchmark_bars = bars if symbol.upper() == request.benchmark_symbol.upper() else self._benchmark_bars(request)
        training_features = enrich_with_tactical_context(training_features, bars, benchmark_bars)
        live_features = enrich_with_tactical_context(live_features, bars, benchmark_bars)

        model = train_model(training_features, purge=request.horizon)
        live_row = live_features.iloc[[-1]]
        predicted_return = float(model.predict(live_row)[0])
        probability_profitable = float(model.predict_probability(live_row)[0])
        signal = make_signal(
            predicted_return,
            buy_threshold=request.buy_threshold,
            sell_threshold=request.sell_threshold,
            round_trip_cost=request.round_trip_cost,
            calibrated_probability=probability_profitable,
        )
        return SymbolAnalysis(
            symbol,
            bars,
            training_features,
            live_features,
            model,
            float(bars["Close"].iloc[-1]),
            bars.index[-1],
            predicted_return,
            signal,
            request.horizon,
            context_bars,
            current_regime,
            probability_profitable,
        )

    def analyze_watchlist(self, symbols: list[str], request: AnalysisRequest) -> WatchlistAnalysis:
        available: dict[str, SymbolAnalysis] = {}
        unavailable: dict[str, str] = {}
        for symbol in symbols:
            try:
                available[symbol] = self.analyze_symbol(symbol, request)
            except (RuntimeError, ValueError) as exc:
                unavailable[symbol] = str(exc)
        return WatchlistAnalysis(available, unavailable)

    def validation_scores(self, analysis: SymbolAnalysis, splits: int = 3) -> list[dict[str, float]]:
        return walk_forward_scores(analysis.training_features, splits=splits, purge=analysis.horizon)

    def benchmark_report(self, analysis: SymbolAnalysis, splits: int = 3) -> tuple[list[dict[str, float | str]], ModelGate]:
        rows = benchmark_models(analysis.training_features, splits=splits, purge=analysis.horizon)
        return rows, assess_model_gate(rows)

    def backtest(self, analysis: SymbolAnalysis, request: AnalysisRequest, starting_cash: float, test_fraction: float = 0.2) -> dict:
        features = analysis.training_features
        train_end = max(int(len(features) * (1.0 - test_fraction)), 1)
        test_start = train_end + analysis.horizon
        train_features = features.iloc[:train_end]
        test_features = features.iloc[test_start:]
        if len(train_features) < 20 or len(test_features) < 2:
            raise ValueError("Not enough rows for a purged holdout backtest")
        from ..modeling import fit_model

        backtest_model = fit_model(train_features)
        predicted = pd.Series(backtest_model.predict(test_features), index=test_features.index, dtype=float)
        return run_backtest(
            analysis.symbol,
            analysis.bars.loc[test_features.index],
            predicted,
            starting_cash=starting_cash,
            commission_rate=request.commission_rate,
            slippage_rate=request.slippage_rate,
            buy_threshold=request.buy_threshold,
            sell_threshold=request.sell_threshold,
        )
