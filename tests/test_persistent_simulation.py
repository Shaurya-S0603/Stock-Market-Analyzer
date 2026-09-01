from __future__ import annotations

from pathlib import Path

import pytest

from stockmarket.config import Settings
from stockmarket.services import PersistentPaperState, PortfolioService
from stockmarket.simulation_worker import run_one_cycle
from stockmarket.storage import Store
from stockmarket.trading import PaperPortfolio


def test_persistent_paper_state_round_trips_account_and_positions(tmp_path: Path) -> None:
    db = tmp_path / "paper.db"
    state = PersistentPaperState(db)
    portfolio = PaperPortfolio(10_000, commission_rate=0.001, slippage_rate=0.0005)
    portfolio.execute("MSFT", "buy", 5, 100)
    state.save(portfolio)

    restored = state.load(10_000, 0.001, 0.0005)
    assert restored is not None
    assert restored.cash == pytest.approx(portfolio.cash)
    assert restored.positions["MSFT"].quantity == 5
    assert restored.positions["MSFT"].average_cost == pytest.approx(portfolio.positions["MSFT"].average_cost)


def test_portfolio_service_persists_after_each_paper_fill(tmp_path: Path) -> None:
    db = tmp_path / "paper.db"
    store = Store(str(db))
    state = PersistentPaperState(db)
    portfolio = PaperPortfolio(10_000, commission_rate=0.0, slippage_rate=0.0)
    service = PortfolioService(portfolio, store, state)

    service.execute("AAPL", "buy", 3, 100, reason="test")
    restored = state.load(10_000, 0.0, 0.0)
    assert restored is not None
    assert restored.cash == pytest.approx(9_700)
    assert restored.positions["AAPL"].quantity == 3

    service.execute("AAPL", "sell", 1, 110, reason="test_exit")
    restored_again = state.load(10_000, 0.0, 0.0)
    assert restored_again is not None
    assert restored_again.positions["AAPL"].quantity == 2
    assert restored_again.positions["AAPL"].realized_pnl == pytest.approx(10)


def test_worker_checkpoint_is_durable(tmp_path: Path) -> None:
    db = tmp_path / "paper.db"
    state = PersistentPaperState(db)
    state.record_worker_checkpoint("abc123", "executed")
    reopened = PersistentPaperState(db)
    checkpoint = reopened.worker_checkpoint()
    assert checkpoint["last_fingerprint"] == "abc123"
    assert checkpoint["last_status"] == "executed"


def test_worker_exits_cleanly_when_no_portfolio_profile_exists(tmp_path: Path) -> None:
    result = run_one_cycle(
        db_path=tmp_path / "worker.db",
        settings=Settings(starting_cash=10_000),
    )
    assert result.status == "no_profile"
    assert result.executed_trades == 0
    assert result.symbols_evaluated == 0


def test_persistent_state_rejects_incompatible_account_configuration(tmp_path: Path) -> None:
    db = tmp_path / "paper.db"
    state = PersistentPaperState(db)
    state.save(PaperPortfolio(10_000, commission_rate=0.001, slippage_rate=0.0005))
    assert state.load(20_000, 0.001, 0.0005) is None
    assert state.load(10_000, 0.002, 0.0005) is None
