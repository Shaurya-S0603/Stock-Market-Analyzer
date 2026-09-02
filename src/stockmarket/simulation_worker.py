from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path

from .config import Settings
from .data import YahooFinanceProvider
from .services import (
    AITraderConfig,
    AnalysisRequest,
    AnalysisService,
    JournalService,
    PaperOnlyPortfolioStrategy,
    PersistentPaperState,
    PortfolioCycleService,
    PortfolioService,
    RiskLimits,
    RiskPolicy,
    TraderMode,
    cycle_fingerprint,
)
from .storage import Store
from .trading import PaperPortfolio


@dataclass(frozen=True)
class WorkerCycleResult:
    status: str
    mode: str
    symbols_evaluated: int
    decisions: int
    executed_trades: int
    cash: float
    equity: float
    fingerprint: str | None
    unavailable: dict[str, str]


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _risk_config(profile: str, mode: TraderMode, largest_allocation: float) -> AITraderConfig:
    profiles: dict[str, dict[str, float | int]] = {
        "Conservative": {
            "min_confidence": 0.75, "max_position_pct": 8.0, "max_portfolio_exposure_pct": 50.0,
            "max_open_positions": 5, "max_daily_trades": 8, "max_daily_loss_pct": 2.0,
            "volatility_target_pct": 1.0, "max_pairwise_correlation": 0.80, "correlation_penalty_floor": 0.25,
        },
        "Balanced": {
            "min_confidence": 0.58, "max_position_pct": 12.0, "max_portfolio_exposure_pct": 70.0,
            "max_open_positions": 8, "max_daily_trades": 16, "max_daily_loss_pct": 3.0,
            "volatility_target_pct": 1.75, "max_pairwise_correlation": 0.92, "correlation_penalty_floor": 0.40,
        },
        "Aggressive": {
            "min_confidence": 0.55, "max_position_pct": 15.0, "max_portfolio_exposure_pct": 75.0,
            "max_open_positions": 8, "max_daily_trades": 18, "max_daily_loss_pct": 5.0,
            "volatility_target_pct": 2.0, "max_pairwise_correlation": 0.95, "correlation_penalty_floor": 0.50,
        },
    }
    values = profiles.get(profile, profiles["Balanced"])
    min_confidence = float(os.getenv("PAPER_MIN_CONFIDENCE", values["min_confidence"]))
    entry_pct = float(os.getenv("PAPER_ENTRY_ALLOCATION_PCT", max(0.5, min(25.0, largest_allocation))))
    return AITraderConfig(
        mode=mode,
        min_confidence=min_confidence,
        allocation_pct=entry_pct,
        risk_limits=RiskLimits(
            max_position_pct=float(values["max_position_pct"]),
            max_portfolio_exposure_pct=float(values["max_portfolio_exposure_pct"]),
            max_open_positions=int(values["max_open_positions"]),
            max_daily_trades=int(values["max_daily_trades"]),
            max_daily_loss_pct=float(values["max_daily_loss_pct"]),
            volatility_target_pct=float(values["volatility_target_pct"]),
            max_pairwise_correlation=float(values["max_pairwise_correlation"]),
            correlation_penalty_floor=float(values["correlation_penalty_floor"]),
        ),
    )


def _portfolio_signature(portfolio: PaperPortfolio) -> tuple:
    positions = tuple(
        sorted(
            (symbol, int(position.quantity), round(float(position.average_cost), 8))
            for symbol, position in portfolio.positions.items()
            if position.quantity > 0
        )
    )
    return (round(float(portfolio.cash), 8), positions)


def _worker_fingerprint(analyses: dict, config: AITraderConfig, allocations: dict[str, float], portfolio: PaperPortfolio) -> str:
    payload = (
        cycle_fingerprint(analyses, config),
        tuple(sorted((symbol, round(float(weight), 6)) for symbol, weight in allocations.items())),
        _portfolio_signature(portfolio),
    )
    return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()


def run_one_cycle(
    *,
    provider=None,
    db_path: str | Path | None = None,
    settings: Settings | None = None,
    mode: TraderMode | str | None = None,
) -> WorkerCycleResult:
    """Run one deterministic paper-strategy cycle. Safe to call from an external scheduler."""
    settings = settings or Settings.from_environment()
    settings.validate()
    path = Path(db_path or os.getenv("PAPER_DB_PATH", ".data/paper_trading.db"))
    store = Store(str(path))
    profile = store.portfolio_profile()
    if not profile or not profile.get("allocations"):
        return WorkerCycleResult("no_profile", TraderMode.OFF.value, 0, 0, 0, 0.0, 0.0, None, {})

    allocations = {str(symbol).upper(): float(weight) for symbol, weight in profile["allocations"].items()}
    symbols = list(allocations)
    starting_cash = float(profile["starting_capital"])
    paper_state = PersistentPaperState(path)
    portfolio = paper_state.load(starting_cash, settings.commission_rate, settings.slippage_rate)
    if portfolio is None:
        portfolio = PaperPortfolio(starting_cash, settings.commission_rate, settings.slippage_rate)
        paper_state.save(portfolio)
    portfolio_service = PortfolioService(portfolio, store, paper_state)

    raw_mode = mode or os.getenv("PAPER_TRADER_MODE") or profile.get("trader_mode", TraderMode.OBSERVE.value)
    try:
        trader_mode = raw_mode if isinstance(raw_mode, TraderMode) else TraderMode(str(raw_mode))
    except ValueError:
        trader_mode = TraderMode.OBSERVE
    config = _risk_config(str(profile.get("risk_profile", "Balanced")), trader_mode, max(allocations.values(), default=5.0))
    config.validate()
    if trader_mode == TraderMode.OFF:
        equity = portfolio.equity({})
        paper_state.record_worker_checkpoint(None, "inactive")
        return WorkerCycleResult("inactive", trader_mode.value, 0, 0, 0, portfolio.cash, equity, None, {})

    request = AnalysisRequest(
        period=settings.period,
        interval=settings.interval,
        horizon=settings.horizon,
        buy_threshold=settings.buy_threshold,
        sell_threshold=settings.sell_threshold,
        commission_rate=settings.commission_rate,
        slippage_rate=settings.slippage_rate,
    )
    analysis_service = AnalysisService(provider or YahooFinanceProvider())
    result = analysis_service.analyze_watchlist(symbols, request)
    prices = {symbol: float(analysis.price) for symbol, analysis in result.available.items()}
    if not result.available:
        paper_state.record_worker_checkpoint(None, "no_data")
        return WorkerCycleResult("no_data", trader_mode.value, 0, 0, 0, portfolio.cash, portfolio.equity(prices), None, result.unavailable)

    initial_fingerprint = _worker_fingerprint(result.available, config, allocations, portfolio)
    checkpoint = paper_state.worker_checkpoint()
    if checkpoint.get("last_fingerprint") == initial_fingerprint:
        return WorkerCycleResult(
            "unchanged", trader_mode.value, len(result.available), 0, 0,
            portfolio.cash, portfolio.equity(prices), initial_fingerprint, result.unavailable,
        )

    exit_policy = RiskPolicy(enabled=_truthy(os.getenv("PAPER_ADAPTIVE_EXITS", "0")))
    portfolio_service.apply_adaptive_exit_policy(result.available, exit_policy)
    research_cycle = PortfolioCycleService(analysis_service).run(symbols, request, allocations, watchlist=result)
    strategy = PaperOnlyPortfolioStrategy().run(research_cycle, portfolio_service, config)
    decisions = strategy.decisions
    JournalService(store).record_cycle(decisions, trader_mode, portfolio, prices)
    portfolio_service.persist_state()

    final_fingerprint = _worker_fingerprint(result.available, config, allocations, portfolio)
    executed = sum(1 for decision in decisions if bool(decision.executed))
    paper_state.record_worker_checkpoint(final_fingerprint, "executed")
    return WorkerCycleResult(
        "executed", trader_mode.value, len(result.available), len(decisions), executed,
        portfolio.cash, portfolio.equity(prices), final_fingerprint, result.unavailable,
    )


def main() -> int:
    result = run_one_cycle()
    print(json.dumps(asdict(result), sort_keys=True))
    return 0 if result.status not in {"no_profile", "no_data"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
