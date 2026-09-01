from __future__ import annotations

import pandas as pd

from ..trading import PaperPortfolio
from .portfolio_cycle import PortfolioResearchCycle


def build_return_correlation_matrix(cycle: PortfolioResearchCycle, window: int = 120) -> pd.DataFrame:
    """Build a return-correlation matrix when usable market history is available.

    Correlation is a portfolio-risk enhancement, not a prerequisite for the
    strategy engine. Lightweight analyses used by tests or offline callers may
    omit bar history; those symbols are skipped and therefore receive no
    correlation penalty instead of crashing the portfolio cycle.
    """
    if window < 20:
        raise ValueError("correlation window must be at least 20 bars")

    returns: dict[str, pd.Series] = {}
    for symbol, state in cycle.states.items():
        analysis = getattr(state, "analysis", None)
        bars = getattr(analysis, "bars", None)
        if not isinstance(bars, pd.DataFrame) or "Close" not in bars.columns:
            continue
        close = pd.to_numeric(bars["Close"], errors="coerce").sort_index().dropna()
        if len(close) < 11:
            continue
        series = close.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna().tail(window)
        if len(series) >= 10:
            returns[str(symbol).upper()] = series

    if not returns:
        return pd.DataFrame(dtype=float)
    if len(returns) == 1:
        symbol = next(iter(returns))
        return pd.DataFrame([[1.0]], index=[symbol], columns=[symbol], dtype=float)

    frame = pd.concat(returns, axis=1).dropna(how="all")
    if len(frame) < 10:
        return pd.DataFrame(index=returns, columns=returns, dtype=float)
    matrix = frame.corr(min_periods=10)
    for symbol in matrix.index.intersection(matrix.columns):
        matrix.loc[symbol, symbol] = 1.0
    return matrix


def candidate_portfolio_correlation(
    symbol: str,
    matrix: pd.DataFrame,
    portfolio: PaperPortfolio,
    additional_symbols: list[str] | None = None,
) -> float:
    symbol = symbol.upper()
    if matrix.empty or symbol not in matrix.index:
        return 0.0
    comparators = [
        ticker
        for ticker, position in portfolio.positions.items()
        if position.quantity > 0 and ticker != symbol and ticker in matrix.columns
    ]
    for ticker in additional_symbols or []:
        ticker = ticker.upper()
        if ticker != symbol and ticker in matrix.columns and ticker not in comparators:
            comparators.append(ticker)
    if not comparators:
        return 0.0
    values = pd.to_numeric(matrix.loc[symbol, comparators], errors="coerce").abs().dropna()
    return float(values.max()) if not values.empty else 0.0
