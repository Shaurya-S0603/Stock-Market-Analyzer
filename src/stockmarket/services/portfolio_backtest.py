from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..modeling import fit_model
from ..trading import PaperPortfolio, TradingError
from ..validation import purged_walk_forward_splits


@dataclass(frozen=True)
class PortfolioFoldResult:
    fold: int
    train_rows: int
    test_rows: int
    strategy_return_pct: float
    benchmark_return_pct: float
    excess_return_pct: float
    max_drawdown_pct: float
    trades: int
    ending_equity: float


@dataclass(frozen=True)
class PortfolioWalkForwardReport:
    folds: list[PortfolioFoldResult]
    mean_strategy_return_pct: float
    mean_benchmark_return_pct: float
    mean_excess_return_pct: float
    worst_drawdown_pct: float
    total_trades: int


def _common_feature_index(analyses: dict) -> pd.DatetimeIndex:
    common: pd.DatetimeIndex | None = None
    for analysis in analyses.values():
        index = pd.DatetimeIndex(analysis.training_features.index)
        common = index if common is None else common.intersection(index)
    if common is None or len(common) == 0:
        raise ValueError("No common training timestamps are available across the portfolio")
    return common.sort_values()


def _drawdown(equity: list[float]) -> float:
    values = np.asarray(equity, dtype=float)
    if len(values) == 0:
        return 0.0
    peaks = np.maximum.accumulate(values)
    drawdowns = values / np.where(peaks == 0, 1.0, peaks) - 1.0
    return float(drawdowns.min() * 100.0)


def _benchmark_return(analyses: dict, allocations: dict[str, float], timestamps: pd.DatetimeIndex) -> float:
    if len(timestamps) < 2:
        return 0.0
    total = 0.0
    for symbol, analysis in analyses.items():
        weight = max(float(allocations.get(symbol, 0.0)), 0.0) / 100.0
        if weight <= 0:
            continue
        close = pd.to_numeric(analysis.bars["Close"], errors="coerce").reindex(timestamps).dropna()
        if len(close) >= 2 and close.iloc[0] > 0:
            total += weight * (float(close.iloc[-1]) / float(close.iloc[0]) - 1.0)
    return total * 100.0


def run_portfolio_walk_forward(
    analyses: dict,
    allocations: dict[str, float],
    *,
    starting_cash: float = 100_000.0,
    commission_rate: float = 0.001,
    slippage_rate: float = 0.0005,
    buy_threshold: float = 0.005,
    sell_threshold: float = -0.005,
    max_exposure_pct: float = 60.0,
    max_pairwise_correlation: float = 0.90,
    splits: int = 3,
) -> PortfolioWalkForwardReport:
    if not analyses:
        raise ValueError("At least one symbol analysis is required")
    common_index = _common_feature_index(analyses)
    purge = max(int(getattr(analysis, "horizon", 1)) for analysis in analyses.values())
    folds = purged_walk_forward_splits(len(common_index), splits=splits, purge=purge, minimum_train_rows=30, minimum_test_rows=8)
    round_trip_cost = 2.0 * (commission_rate + slippage_rate)
    results: list[PortfolioFoldResult] = []

    for fold in folds:
        train_times = common_index[fold.train_start : fold.train_end]
        test_times = common_index[fold.test_start : fold.test_end]
        models = {}
        predictions: dict[str, pd.Series] = {}
        train_returns: dict[str, pd.Series] = {}
        for symbol, analysis in analyses.items():
            train = analysis.training_features.reindex(train_times).dropna()
            test = analysis.training_features.reindex(test_times).dropna()
            if len(train) < 20 or len(test) < 2:
                continue
            models[symbol] = fit_model(train)
            predictions[symbol] = pd.Series(models[symbol].predict(test), index=test.index, dtype=float)
            train_close = pd.to_numeric(analysis.bars["Close"], errors="coerce").reindex(train_times)
            train_returns[symbol] = train_close.pct_change()
        if not predictions:
            continue

        corr = pd.concat(train_returns, axis=1).corr(min_periods=10) if train_returns else pd.DataFrame()
        portfolio = PaperPortfolio(starting_cash, commission_rate, slippage_rate)
        equity_curve: list[float] = []
        trades = 0

        for i in range(len(test_times) - 1):
            signal_time = test_times[i]
            execution_time = test_times[i + 1]
            prices_close: dict[str, float] = {}
            prices_open: dict[str, float] = {}
            for symbol, analysis in analyses.items():
                if execution_time not in analysis.bars.index:
                    continue
                prices_close[symbol] = float(analysis.bars.loc[execution_time, "Close"])
                prices_open[symbol] = float(analysis.bars.loc[execution_time, "Open"])

            # Exit first so released simulated cash can fund a later candidate.
            for symbol, position in list(portfolio.positions.items()):
                if position.quantity <= 0 or symbol not in predictions or signal_time not in predictions[symbol].index:
                    continue
                if float(predictions[symbol].loc[signal_time]) - round_trip_cost <= sell_threshold and symbol in prices_open:
                    try:
                        portfolio.execute(symbol, "sell", position.quantity, prices_open[symbol], execution_time, reason="portfolio_walk_forward_exit")
                        trades += 1
                    except TradingError:
                        pass

            candidates = []
            for symbol, series in predictions.items():
                if signal_time not in series.index or symbol not in prices_open:
                    continue
                position = portfolio.positions.get(symbol)
                if position and position.quantity > 0:
                    continue
                net_edge = float(series.loc[signal_time]) - round_trip_cost
                if net_edge >= buy_threshold and float(allocations.get(symbol, 0.0)) > 0:
                    candidates.append((net_edge, symbol))
            candidates.sort(reverse=True)

            for net_edge, symbol in candidates:
                equity = portfolio.equity(prices_close)
                current_exposure = sum(
                    position.quantity * prices_close.get(ticker, position.average_cost)
                    for ticker, position in portfolio.positions.items()
                    if position.quantity > 0
                )
                if equity <= 0 or current_exposure / equity * 100.0 >= max_exposure_pct:
                    break
                existing = [ticker for ticker, position in portfolio.positions.items() if position.quantity > 0 and ticker in corr.columns]
                if existing and symbol in corr.index:
                    pair_values = pd.to_numeric(corr.loc[symbol, existing], errors="coerce").abs().dropna()
                    if not pair_values.empty and float(pair_values.max()) > max_pairwise_correlation:
                        continue
                cap_pct = min(float(allocations.get(symbol, 0.0)), max_exposure_pct)
                symbol_budget = equity * cap_pct / 100.0
                exposure_room = max(equity * max_exposure_pct / 100.0 - current_exposure, 0.0)
                budget = min(symbol_budget, exposure_room, portfolio.cash)
                unit_cost = prices_open[symbol] * (1.0 + slippage_rate) * (1.0 + commission_rate)
                quantity = int(budget / unit_cost) if unit_cost > 0 else 0
                if quantity < 1:
                    continue
                try:
                    portfolio.execute(symbol, "buy", quantity, prices_open[symbol], execution_time, reason="portfolio_walk_forward_entry")
                    trades += 1
                except TradingError:
                    continue

            equity_curve.append(portfolio.equity(prices_close))

        if not equity_curve:
            continue
        strategy_return = (equity_curve[-1] / starting_cash - 1.0) * 100.0
        benchmark_return = _benchmark_return(analyses, allocations, test_times)
        results.append(
            PortfolioFoldResult(
                fold=fold.fold,
                train_rows=fold.train_rows,
                test_rows=fold.test_rows,
                strategy_return_pct=float(strategy_return),
                benchmark_return_pct=float(benchmark_return),
                excess_return_pct=float(strategy_return - benchmark_return),
                max_drawdown_pct=_drawdown(equity_curve),
                trades=trades,
                ending_equity=float(equity_curve[-1]),
            )
        )

    if not results:
        raise ValueError("No portfolio walk-forward fold produced a valid simulation")
    return PortfolioWalkForwardReport(
        folds=results,
        mean_strategy_return_pct=float(np.mean([row.strategy_return_pct for row in results])),
        mean_benchmark_return_pct=float(np.mean([row.benchmark_return_pct for row in results])),
        mean_excess_return_pct=float(np.mean([row.excess_return_pct for row in results])),
        worst_drawdown_pct=float(min(row.max_drawdown_pct for row in results)),
        total_trades=int(sum(row.trades for row in results)),
    )
