from __future__ import annotations

import pandas as pd

from ..trading import PaperPortfolio
from .portfolio_cycle import PortfolioResearchCycle


def build_return_correlation_matrix(cycle: PortfolioResearchCycle, window: int = 120) -> pd.DataFrame:
    if window < 20:
        raise ValueError("correlation window must be at least 20 bars")
    returns: dict[str, pd.Series] = {}
    for symbol, state in cycle.states.items():
        close = pd.to_numeric(state.analysis.bars["Close"], errors="coerce").sort_index()
        returns[symbol] = close.pct_change().tail(window)
    if not returns:
        return pd.DataFrame()
    frame = pd.concat(returns, axis=1).dropna(how="all")
    if len(frame) < 10:
        return pd.DataFrame(index=returns, columns=returns, dtype=float)
    return frame.corr(min_periods=10)


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
