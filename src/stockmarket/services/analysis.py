from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from ..backtest import run_backtest
from ..features import build_features
from ..modeling import ModelResult, train_model, walk_forward_scores
from ..signals import Signal, make_signal


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

    @property
    def round_trip_cost(self) -> float:
        return 2.0 * (self.commission_rate + self.slippage_rate)


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


@dataclass
class WatchlistAnalysis:
    available: dict[str, SymbolAnalysis]
    unavailable: dict[str, str]


class AnalysisService:
    """Application-layer orchestration for market research workflows."""

    def __init__(self, provider: MarketProvider):
        self.provider = provider

    def analyze_symbol(self, symbol: str, request: AnalysisRequest) -> SymbolAnalysis:
        bars = self.provider.fetch(symbol, request.period, request.interval)
        training_features = build_features(bars, horizon=request.horizon, include_target=True)
        live_features = build_features(bars, horizon=request.horizon, include_target=False)
        model = train_model(training_features)
        latest_features = live_features.iloc[[-1]]
        predicted_return = float(model.predict(latest_features)[0])
        signal = make_signal(
            predicted_return,
            buy_threshold=request.buy_threshold,
            sell_threshold=request.sell_threshold,
            round_trip_cost=request.round_trip_cost,
        )
        return SymbolAnalysis(
            symbol=symbol,
            bars=bars,
            training_features=training_features,
            live_features=live_features,
            model=model,
            price=float(bars["Close"].iloc[-1]),
            timestamp=bars.index[-1],
            predicted_return=predicted_return,
            signal=signal,
        )

    def analyze_watchlist(self, symbols: list[str], request: AnalysisRequest) -> WatchlistAnalysis:
        available: dict[str, SymbolAnalysis] = {}
        unavailable: dict[str, str] = {}
        for symbol in symbols:
            try:
                available[symbol] = self.analyze_symbol(symbol, request)
            except (RuntimeError, ValueError) as exc:
                unavailable[symbol] = str(exc)
        return WatchlistAnalysis(available=available, unavailable=unavailable)

    def validation_scores(self, analysis: SymbolAnalysis, splits: int = 3) -> list[dict[str, float]]:
        return walk_forward_scores(analysis.training_features, splits=splits)

    def backtest(
        self,
        analysis: SymbolAnalysis,
        request: AnalysisRequest,
        starting_cash: float,
        test_fraction: float = 0.2,
    ) -> dict:
        features = analysis.training_features
        split = max(int(len(features) * (1.0 - test_fraction)), 1)
        test_features = features.iloc[split:]
        if len(test_features) < 2:
            raise ValueError("Not enough holdout rows for a backtest")
        predicted = pd.Series(
            analysis.model.predict(test_features),
            index=test_features.index,
            dtype=float,
        )
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
