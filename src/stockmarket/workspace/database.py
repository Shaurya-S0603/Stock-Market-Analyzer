"""Non-destructive SQLite persistence for market candles and named watchlists."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import (
    Column, Float, ForeignKey, ForeignKeyConstraint, Integer, MetaData,
    String, Table, create_engine, delete, event, insert, select, update,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

metadata = MetaData()
symbols = Table(
    "workspace_symbols", metadata,
    Column("symbol", String(40), primary_key=True),
    Column("name", String(240)),
    Column("exchange", String(80)),
    Column("currency", String(12)),
    Column("provider", String(80), nullable=False),
    Column("updated_at", String(40), nullable=False),
)
candles = Table(
    "workspace_ohlcv", metadata,
    Column("symbol", String(40), ForeignKey("workspace_symbols.symbol"), primary_key=True),
    Column("interval", String(10), primary_key=True),
    Column("timestamp", String(40), primary_key=True),
    Column("open", Float, nullable=False),
    Column("high", Float, nullable=False),
    Column("low", Float, nullable=False),
    Column("close", Float, nullable=False),
    Column("volume", Float, nullable=False),
    Column("provider", String(80), nullable=False),
    Column("adjustment_mode", String(32), nullable=False),
    Column("retrieved_at", String(40), nullable=False),
)
watchlists = Table(
    "workspace_watchlists", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False, unique=True),
    Column("created_at", String(40), nullable=False),
)
watchlist_items = Table(
    "workspace_watchlist_items", metadata,
    Column("watchlist_id", Integer, ForeignKey("workspace_watchlists.id", ondelete="CASCADE"), primary_key=True),
    Column("symbol", String(40), ForeignKey("workspace_symbols.symbol"), primary_key=True),
)
schema_versions = Table(
    "workspace_schema_versions", metadata,
    Column("version", Integer, primary_key=True),
    Column("applied_at", String(40), nullable=False),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_symbol(value: str) -> str:
    symbol = str(value).strip().upper()
    if not symbol or len(symbol) > 40 or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-^=" for char in symbol):
        raise ValueError("Enter a valid market symbol using letters, digits, '.', '-', '^' or '='.")
    return symbol


class WorkspaceDB:
    """Owns new workspace tables without touching existing QuantEdge paper tables."""

    def __init__(self, path: str | None = None):
        self.path = str(path or os.getenv("QUANTEDGE_WORKSPACE_DB", ".data/workspace.db"))
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            "sqlite:///" + str(Path(self.path).resolve()),
            connect_args={"check_same_thread": False, "timeout": 10},
            future=True,
        )

        @event.listens_for(self.engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.execute(sqlite_insert(schema_versions).values(version=1, applied_at=utc_now()).on_conflict_do_nothing())

    def register_symbol(self, symbol: str, *, provider: str = "manual",
                        name: str | None = None, exchange: str | None = None,
                        currency: str | None = None) -> str:
        clean = clean_symbol(symbol)
        with self.engine.begin() as conn:
            conn.execute(sqlite_insert(symbols).values(
                symbol=clean, name=name, exchange=exchange, currency=currency,
                provider=provider, updated_at=utc_now(),
            ).on_conflict_do_nothing(index_elements=["symbol"]))
        return clean

    def save_candles(self, symbol: str, interval: str, frame: pd.DataFrame,
                     *, provider: str, adjustment_mode: str = "raw") -> int:
        clean = self.register_symbol(symbol, provider=provider)
        if frame.empty or not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
            raise ValueError("Historical candles require a nonempty timezone-aware index")
        if frame.index.has_duplicates:
            raise ValueError("Duplicate candle timestamps are not permitted")
        now = utc_now()
        rows = []
        for timestamp, row in frame.iterrows():
            rows.append({
                "symbol": clean, "interval": interval,
                "timestamp": timestamp.tz_convert("UTC").isoformat(),
                "open": float(row["open"]), "high": float(row["high"]),
                "low": float(row["low"]), "close": float(row["close"]),
                "volume": float(row["volume"]), "provider": provider,
                "adjustment_mode": adjustment_mode, "retrieved_at": now,
            })
        with self.engine.begin() as conn:
            statement = sqlite_insert(candles)
            for row in rows:
                conn.execute(statement.values(**row).on_conflict_do_update(
                    index_elements=["symbol", "interval", "timestamp"],
                    set_={key: value for key, value in row.items() if key not in ("symbol", "interval", "timestamp")},
                ))
        return len(rows)

    def load_candles(self, symbol: str, interval: str) -> pd.DataFrame:
        clean = clean_symbol(symbol)
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(candles).where(candles.c.symbol == clean, candles.c.interval == interval)
                .order_by(candles.c.timestamp)
            ).mappings().all()
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(rows)
        frame.index = pd.to_datetime(frame.pop("timestamp"), utc=True)
        frame.index.name = "timestamp"
        return frame

    def cached_symbols(self) -> list[str]:
        with self.engine.connect() as conn:
            return list(conn.execute(select(symbols.c.symbol).order_by(symbols.c.symbol)).scalars().all())

    def list_watchlists(self) -> list[dict]:
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(
                select(watchlists).order_by(watchlists.c.name)
            ).mappings().all()]

    def create_watchlist(self, name: str) -> int:
        label = str(name).strip()
        if not label or len(label) > 100:
            raise ValueError("Watchlist name must contain 1 to 100 characters")
        with self.engine.begin() as conn:
            if conn.execute(select(watchlists.c.id).where(watchlists.c.name == label)).scalar_one_or_none() is not None:
                raise ValueError("A watchlist with that name already exists")
            result = conn.execute(insert(watchlists).values(name=label, created_at=utc_now()))
            return int(result.inserted_primary_key[0])

    def default_watchlist(self) -> int:
        lists = self.list_watchlists()
        return int(lists[0]["id"]) if lists else self.create_watchlist("My Watchlist")

    def rename_watchlist(self, list_id: int, name: str) -> None:
        label = str(name).strip()
        if not label or len(label) > 100:
            raise ValueError("Watchlist name must contain 1 to 100 characters")
        with self.engine.begin() as conn:
            if conn.execute(select(watchlists.c.id).where(watchlists.c.name == label, watchlists.c.id != list_id)).first():
                raise ValueError("A watchlist with that name already exists")
            result = conn.execute(update(watchlists).where(watchlists.c.id == list_id).values(name=label))
            if not result.rowcount:
                raise ValueError("Watchlist not found")

    def delete_watchlist(self, list_id: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(watchlists).where(watchlists.c.id == list_id))

    def add_to_watchlist(self, list_id: int, symbol: str) -> None:
        clean = self.register_symbol(symbol)
        with self.engine.begin() as conn:
            if not conn.execute(select(watchlists.c.id).where(watchlists.c.id == list_id)).scalar_one_or_none():
                raise ValueError("Watchlist not found")
            conn.execute(sqlite_insert(watchlist_items).values(
                watchlist_id=list_id, symbol=clean
            ).on_conflict_do_nothing())

    def remove_from_watchlist(self, list_id: int, symbol: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(watchlist_items).where(
                watchlist_items.c.watchlist_id == list_id,
                watchlist_items.c.symbol == clean_symbol(symbol),
            ))

    def symbols_in_watchlist(self, list_id: int) -> list[str]:
        with self.engine.connect() as conn:
            return list(conn.execute(select(watchlist_items.c.symbol).where(
                watchlist_items.c.watchlist_id == list_id
            ).order_by(watchlist_items.c.symbol)).scalars().all())
