from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path: str = "paper_trading.db"):
        self.path = Path(path)
        with sqlite3.connect(self.path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, symbol TEXT, side TEXT, quantity INTEGER, price REAL, fee REAL, realized_pnl REAL DEFAULT 0, reason TEXT DEFAULT 'manual', created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            connection.execute("CREATE TABLE IF NOT EXISTS model_runs (id INTEGER PRIMARY KEY, symbol TEXT, metrics TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            self._ensure_orders_schema(connection)

    @staticmethod
    def _ensure_orders_schema(connection: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(orders)").fetchall()
        }
        if "realized_pnl" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN realized_pnl REAL DEFAULT 0")
        if "reason" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN reason TEXT DEFAULT 'manual'")

    def add_order(self, symbol: str, side: str, quantity: int, price: float, fee: float, realized_pnl: float = 0.0, reason: str = "manual") -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO orders(symbol, side, quantity, price, fee, realized_pnl, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (symbol, side, quantity, price, fee, realized_pnl, reason),
            )

    def orders(self) -> list[dict]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute("SELECT * FROM orders ORDER BY id DESC")]

    def add_model_run(self, symbol: str, metrics: dict) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO model_runs(symbol, metrics) VALUES (?, ?)", (symbol, json.dumps(metrics)))
