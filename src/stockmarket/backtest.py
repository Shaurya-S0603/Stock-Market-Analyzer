from __future__ import annotations

import pandas as pd

from .signals import make_signal
from .trading import PaperPortfolio, TradingError


def run_backtest(symbol: str, bars: pd.DataFrame, predicted_returns: pd.Series, starting_cash: float = 100_000.0, commission_rate: float = 0.001, slippage_rate: float = 0.0005) -> dict:
    if len(bars) != len(predicted_returns):
        raise ValueError("bars and predictions must have equal length")
    portfolio = PaperPortfolio(starting_cash, commission_rate, slippage_rate)
    equity = []
    trades = 0
    for index in range(len(bars) - 1):
        current = bars.iloc[index]
        next_bar = bars.iloc[index + 1]
        signal = make_signal(float(predicted_returns.iloc[index]), round_trip_cost=commission_rate * 2 + slippage_rate * 2)
        position = portfolio.positions.get(symbol.upper())
        if signal.action == "Buy" and not position:
            quantity = max(int(portfolio.cash * 0.1 / float(next_bar["Open"])), 0)
            if quantity:
                portfolio.execute(symbol, "buy", quantity, float(next_bar["Open"]), bars.index[index + 1])
                trades += 1
        elif signal.action == "Sell" and position and position.quantity:
            portfolio.execute(symbol, "sell", position.quantity, float(next_bar["Open"]), bars.index[index + 1])
            trades += 1
        equity.append(portfolio.equity({symbol.upper(): float(current["Close"])}))
    equity_series = pd.Series(equity, index=bars.index[:-1], dtype=float)
    peak = equity_series.cummax()
    drawdown = (equity_series / peak - 1).min() if len(equity_series) else 0.0
    return {"equity_curve": equity_series, "summary": {"total_return_pct": float((equity_series.iloc[-1] / starting_cash - 1) * 100) if len(equity_series) else 0.0, "max_drawdown_pct": float(drawdown * 100), "trades": trades, "final": portfolio.summary({symbol.upper(): float(bars["Close"].iloc[-1])})}}
