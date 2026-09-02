from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MonteCarloSummary:
    simulations: int
    horizon: int
    median_return_pct: float
    p05_return_pct: float
    p95_return_pct: float
    probability_of_loss: float
    median_max_drawdown_pct: float
    p95_max_drawdown_pct: float


def _max_drawdown(path: np.ndarray) -> float:
    peak = np.maximum.accumulate(path)
    drawdown = path / np.maximum(peak, 1e-12) - 1.0
    return float(drawdown.min() * 100.0)


def run_monte_carlo_stress_test(
    equity_curve: pd.Series | pd.DataFrame,
    simulations: int = 1000,
    horizon: int | None = None,
    block_size: int = 5,
    seed: int = 42,
) -> MonteCarloSummary:
    """Bootstrap strategy returns in short blocks to stress-test outcome dispersion.

    The simulation is descriptive research. It does not estimate guaranteed future
    performance and it never submits or changes paper orders.
    """
    if simulations < 100:
        raise ValueError("simulations must be at least 100")
    if block_size < 1:
        raise ValueError("block_size must be positive")

    if isinstance(equity_curve, pd.DataFrame):
        if "equity" in equity_curve.columns:
            series = equity_curve["equity"]
        elif equity_curve.shape[1] == 1:
            series = equity_curve.iloc[:, 0]
        else:
            raise ValueError("equity_curve DataFrame must contain an equity column")
    else:
        series = equity_curve

    values = pd.to_numeric(series, errors="coerce").dropna()
    if len(values) < 20:
        raise ValueError("At least 20 equity observations are required")
    returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    if len(returns) < 10:
        raise ValueError("At least 10 finite strategy returns are required")

    horizon = int(horizon or len(returns))
    if horizon < 2:
        raise ValueError("horizon must be at least 2")
    block_size = min(int(block_size), len(returns))
    rng = np.random.default_rng(seed)

    terminal_returns: list[float] = []
    drawdowns: list[float] = []
    max_start = max(len(returns) - block_size + 1, 1)
    blocks_needed = int(np.ceil(horizon / block_size))

    for _ in range(simulations):
        starts = rng.integers(0, max_start, size=blocks_needed)
        sampled = np.concatenate([returns[start : start + block_size] for start in starts])[:horizon]
        path = np.cumprod(1.0 + sampled)
        terminal_returns.append(float((path[-1] - 1.0) * 100.0))
        drawdowns.append(_max_drawdown(path))

    terminal = np.asarray(terminal_returns, dtype=float)
    dd = np.asarray(drawdowns, dtype=float)
    return MonteCarloSummary(
        simulations=int(simulations),
        horizon=horizon,
        median_return_pct=float(np.median(terminal)),
        p05_return_pct=float(np.quantile(terminal, 0.05)),
        p95_return_pct=float(np.quantile(terminal, 0.95)),
        probability_of_loss=float(np.mean(terminal < 0.0)),
        median_max_drawdown_pct=float(np.median(dd)),
        p95_max_drawdown_pct=float(np.quantile(dd, 0.05)),
    )
