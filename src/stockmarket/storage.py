from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path: str = ".data/paper_trading.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, side TEXT NOT NULL, quantity INTEGER NOT NULL, price REAL NOT NULL, fee REAL NOT NULL, realized_pnl REAL DEFAULT 0, reason TEXT DEFAULT 'manual', created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            connection.execute("CREATE TABLE IF NOT EXISTS model_runs (id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, metrics TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            connection.execute("CREATE TABLE IF NOT EXISTS ai_trader_runs (id INTEGER PRIMARY KEY, cycle_id TEXT NOT NULL, mode TEXT NOT NULL, symbols_evaluated INTEGER NOT NULL, executed_trades INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            connection.execute("CREATE TABLE IF NOT EXISTS ai_decisions (id INTEGER PRIMARY KEY, cycle_id TEXT NOT NULL, mode TEXT NOT NULL, symbol TEXT NOT NULL, signal TEXT NOT NULL, decision TEXT NOT NULL, quantity INTEGER NOT NULL, price REAL NOT NULL, confidence REAL NOT NULL, predicted_return REAL NOT NULL, net_edge REAL NOT NULL, model_gate_passed INTEGER NOT NULL, reason TEXT NOT NULL, executed INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            connection.execute("CREATE TABLE IF NOT EXISTS portfolio_snapshots (id INTEGER PRIMARY KEY, cash REAL NOT NULL, equity REAL NOT NULL, pnl REAL NOT NULL, exposure_pct REAL NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            connection.execute("CREATE TABLE IF NOT EXISTS risk_events (id INTEGER PRIMARY KEY, symbol TEXT, event_type TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            connection.execute("CREATE TABLE IF NOT EXISTS portfolio_profiles (id INTEGER PRIMARY KEY CHECK (id = 1), name TEXT NOT NULL DEFAULT 'Primary', starting_capital REAL NOT NULL, cash_target_pct REAL NOT NULL, risk_profile TEXT NOT NULL, trader_mode TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            connection.execute("CREATE TABLE IF NOT EXISTS portfolio_allocations (profile_id INTEGER NOT NULL, symbol TEXT NOT NULL, target_weight REAL NOT NULL, max_weight REAL NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(profile_id, symbol), FOREIGN KEY(profile_id) REFERENCES portfolio_profiles(id) ON DELETE CASCADE)")
            self._ensure_orders_schema(connection)

    @staticmethod
    def _ensure_orders_schema(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(orders)").fetchall()}
        if "realized_pnl" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN realized_pnl REAL DEFAULT 0")
        if "reason" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN reason TEXT DEFAULT 'manual'")

    def save_portfolio_profile(
        self,
        *,
        starting_capital: float,
        cash_target_pct: float,
        risk_profile: str,
        trader_mode: str,
        allocations: dict[str, float],
        name: str = "Primary",
    ) -> None:
        clean_allocations = {symbol.strip().upper(): float(weight) for symbol, weight in allocations.items() if symbol.strip()}
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "INSERT INTO portfolio_profiles(id, name, starting_capital, cash_target_pct, risk_profile, trader_mode) VALUES (1, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, starting_capital=excluded.starting_capital, cash_target_pct=excluded.cash_target_pct, risk_profile=excluded.risk_profile, trader_mode=excluded.trader_mode, updated_at=CURRENT_TIMESTAMP",
                (name, float(starting_capital), float(cash_target_pct), risk_profile, trader_mode),
            )
            connection.execute("DELETE FROM portfolio_allocations WHERE profile_id = 1")
            connection.executemany(
                "INSERT INTO portfolio_allocations(profile_id, symbol, target_weight, max_weight, enabled) VALUES (1, ?, ?, ?, 1)",
                [(symbol, weight, weight) for symbol, weight in clean_allocations.items()],
            )

    def portfolio_profile(self) -> dict | None:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM portfolio_profiles WHERE id = 1").fetchone()
            if row is None:
                return None
            profile = dict(row)
            allocation_rows = connection.execute(
                "SELECT symbol, target_weight, max_weight, enabled FROM portfolio_allocations WHERE profile_id = 1 ORDER BY symbol"
            ).fetchall()
            profile["allocations"] = {
                item["symbol"]: float(item["target_weight"])
                for item in allocation_rows
                if int(item["enabled"])
            }
            profile["allocation_rows"] = [dict(item) for item in allocation_rows]
            return profile

    def clear_portfolio_profile(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("DELETE FROM portfolio_profiles WHERE id = 1")

    def add_order(self, symbol: str, side: str, quantity: int, price: float, fee: float, realized_pnl: float = 0.0, reason: str = "manual") -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO orders(symbol, side, quantity, price, fee, realized_pnl, reason) VALUES (?, ?, ?, ?, ?, ?, ?)", (symbol.strip().upper(), side.strip().lower(), quantity, price, fee, realized_pnl, reason))

    def orders(self, limit: int | None = None) -> list[dict]:
        query = "SELECT * FROM orders ORDER BY id DESC"; params: tuple = ()
        if limit is not None:
            query += " LIMIT ?"; params = (int(limit),)
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    def add_model_run(self, symbol: str, metrics: dict[str, float]) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO model_runs(symbol, metrics) VALUES (?, ?)", (symbol.strip().upper(), json.dumps(metrics)))

    def add_trader_run(self, cycle_id: str, mode: str, symbols_evaluated: int, executed_trades: int) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO ai_trader_runs(cycle_id, mode, symbols_evaluated, executed_trades) VALUES (?, ?, ?, ?)", (cycle_id, mode, int(symbols_evaluated), int(executed_trades)))

    def trader_runs(self, limit: int = 100) -> list[dict]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT * FROM ai_trader_runs ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
            return [dict(row) for row in rows]

    def add_ai_decision(self, cycle_id: str, mode: str, decision) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO ai_decisions(cycle_id, mode, symbol, signal, decision, quantity, price, confidence, predicted_return, net_edge, model_gate_passed, reason, executed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (cycle_id, mode, decision.symbol, decision.signal, decision.decision, int(decision.quantity), float(decision.price), float(decision.confidence), float(decision.predicted_return), float(decision.net_edge), int(bool(decision.model_gate_passed)), decision.reason, int(bool(decision.executed))))

    def ai_decisions(self, limit: int = 500) -> list[dict]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT * FROM ai_decisions ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
            return [dict(row) for row in rows]

    def add_portfolio_snapshot(self, cash: float, equity: float, pnl: float, exposure_pct: float) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO portfolio_snapshots(cash, equity, pnl, exposure_pct) VALUES (?, ?, ?, ?)", (float(cash), float(equity), float(pnl), float(exposure_pct)))

    def portfolio_snapshots(self, limit: int = 500) -> list[dict]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT * FROM portfolio_snapshots ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
            return [dict(row) for row in rows]

    def add_risk_event(self, event_type: str, details: str, symbol: str | None = None) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO risk_events(symbol, event_type, details) VALUES (?, ?, ?)", (symbol.upper() if symbol else None, event_type, details))

    def risk_events(self, limit: int = 250) -> list[dict]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT * FROM risk_events ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
            return [dict(row) for row in rows]
