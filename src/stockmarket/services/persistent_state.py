from __future__ import annotations

import sqlite3
from pathlib import Path

from ..trading import PaperPortfolio, Position


class PersistentPaperState:
    """Persists the simulated account and worker checkpoint across process restarts."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS paper_account_state ("
                "id INTEGER PRIMARY KEY CHECK(id = 1), starting_cash REAL NOT NULL, cash REAL NOT NULL, "
                "commission_rate REAL NOT NULL, slippage_rate REAL NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS paper_position_state ("
                "symbol TEXT PRIMARY KEY, quantity INTEGER NOT NULL, average_cost REAL NOT NULL, "
                "realized_pnl REAL NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS simulation_worker_state ("
                "id INTEGER PRIMARY KEY CHECK(id = 1), last_fingerprint TEXT, last_status TEXT NOT NULL DEFAULT 'never', "
                "updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )

    def save(self, portfolio: PaperPortfolio) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO paper_account_state(id, starting_cash, cash, commission_rate, slippage_rate) VALUES (1, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET starting_cash=excluded.starting_cash, cash=excluded.cash, "
                "commission_rate=excluded.commission_rate, slippage_rate=excluded.slippage_rate, updated_at=CURRENT_TIMESTAMP",
                (portfolio.starting_cash, portfolio.cash, portfolio.commission_rate, portfolio.slippage_rate),
            )
            connection.execute("DELETE FROM paper_position_state")
            rows = [
                (symbol, position.quantity, position.average_cost, position.realized_pnl)
                for symbol, position in portfolio.positions.items()
                if position.quantity > 0
            ]
            if rows:
                connection.executemany(
                    "INSERT INTO paper_position_state(symbol, quantity, average_cost, realized_pnl) VALUES (?, ?, ?, ?)",
                    rows,
                )

    def load(self, starting_cash: float, commission_rate: float, slippage_rate: float) -> PaperPortfolio | None:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            account = connection.execute("SELECT * FROM paper_account_state WHERE id = 1").fetchone()
            if account is None:
                return None
            expected = (float(starting_cash), float(commission_rate), float(slippage_rate))
            stored = (
                float(account["starting_cash"]),
                float(account["commission_rate"]),
                float(account["slippage_rate"]),
            )
            if any(abs(a - b) > 1e-12 for a, b in zip(expected, stored)):
                return None
            portfolio = PaperPortfolio(*expected)
            portfolio.cash = float(account["cash"])
            positions = connection.execute("SELECT * FROM paper_position_state ORDER BY symbol").fetchall()
            for row in positions:
                portfolio.positions[str(row["symbol"]).upper()] = Position(
                    quantity=int(row["quantity"]),
                    average_cost=float(row["average_cost"]),
                    realized_pnl=float(row["realized_pnl"]),
                )
            return portfolio

    def worker_checkpoint(self) -> dict[str, str | None]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM simulation_worker_state WHERE id = 1").fetchone()
            if row is None:
                return {"last_fingerprint": None, "last_status": "never", "updated_at": None}
            return dict(row)

    def record_worker_checkpoint(self, fingerprint: str | None, status: str) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO simulation_worker_state(id, last_fingerprint, last_status) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET last_fingerprint=excluded.last_fingerprint, "
                "last_status=excluded.last_status, updated_at=CURRENT_TIMESTAMP",
                (fingerprint, str(status)),
            )

    def reset(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("DELETE FROM paper_position_state")
            connection.execute("DELETE FROM paper_account_state")
            connection.execute("DELETE FROM simulation_worker_state")
