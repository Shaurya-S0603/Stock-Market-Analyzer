"""Atomic, versioned SQLite strategy and reproducible backtest persistence."""
from __future__ import annotations

from hashlib import sha256
import json

import pandas as pd
from sqlalchemy import (
    Column, ForeignKey, Integer, MetaData, String, Table, Text, UniqueConstraint,
    create_engine, delete, insert, select, update,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .database import WorkspaceDB, schema_versions, utc_now
from .strategy_schema import Strategy, parse_strategy

tables = MetaData()
strategies = Table(
    "workspace_strategies", tables,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False, unique=True),
    Column("latest_version", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
)
versions = Table(
    "workspace_strategy_versions", tables,
    Column("strategy_id", Integer, ForeignKey("workspace_strategies.id", ondelete="CASCADE"), primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("definition_json", Text, nullable=False),
    Column("saved_at", String(40), nullable=False),
)
backtests = Table(
    "workspace_strategy_backtests", tables,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("strategy_id", Integer, nullable=True),
    Column("strategy_version", Integer, nullable=True),
    Column("name", String(100), nullable=False),
    Column("data_signature", String(64), nullable=False),
    Column("result_json", Text, nullable=False),
    Column("created_at", String(40), nullable=False),
)


class StrategyRepository:
    def __init__(self, db: WorkspaceDB):
        self.db = db
        tables.create_all(db.engine)
        with db.engine.begin() as conn:
            conn.execute(sqlite_insert(schema_versions).values(
                version=3, applied_at=utc_now()
            ).on_conflict_do_nothing())

    def save(self, definition: Strategy | dict, *, strategy_id: int | None = None) -> dict:
        config = parse_strategy(definition)
        now = utc_now()
        payload = config.model_dump_json()
        with self.db.engine.begin() as conn:
            if strategy_id is None:
                if conn.execute(select(strategies.c.id).where(
                    strategies.c.name == config.name)).first():
                    raise ValueError("Strategy name already exists")
                row = conn.execute(insert(strategies).values(
                    name=config.name, latest_version=1, created_at=now))
                strategy_id = int(row.inserted_primary_key[0])
                version = 1
            else:
                item = conn.execute(select(strategies).where(
                    strategies.c.id == strategy_id)).mappings().first()
                if item is None:
                    raise ValueError("Strategy not found")
                collision = conn.execute(select(strategies.c.id).where(
                    strategies.c.name == config.name, strategies.c.id != strategy_id)).first()
                if collision:
                    raise ValueError("Strategy name already exists")
                version = int(item["latest_version"]) + 1
                conn.execute(update(strategies).where(strategies.c.id == strategy_id).values(
                    name=config.name, latest_version=version))
            conn.execute(insert(versions).values(
                strategy_id=strategy_id, version=version, definition_json=payload,
                saved_at=now))
        return {"id": strategy_id, "version": version, "name": config.name}

    def list_strategies(self) -> list[dict]:
        with self.db.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(strategies).order_by(
                strategies.c.name)).mappings()]

    def load(self, strategy_id: int, version: int | None = None) -> dict:
        with self.db.engine.connect() as conn:
            item = conn.execute(select(strategies).where(
                strategies.c.id == strategy_id)).mappings().first()
            if item is None:
                raise ValueError("Strategy not found")
            number = item["latest_version"] if version is None else version
            record = conn.execute(select(versions).where(
                versions.c.strategy_id == strategy_id, versions.c.version == number
            )).mappings().first()
        if record is None:
            raise ValueError("Strategy version not found")
        return {"id": strategy_id, "version": number,
                "name": item["name"],
                "definition": parse_strategy(record["definition_json"]).model_dump(mode="json")}

    def list_versions(self, strategy_id: int) -> list[int]:
        with self.db.engine.connect() as conn:
            return list(conn.execute(select(versions.c.version).where(
                versions.c.strategy_id == strategy_id).order_by(versions.c.version.desc())).scalars())

    def delete(self, strategy_id: int) -> None:
        # Completed backtests contain immutable snapshots and remain available.
        with self.db.engine.begin() as conn:
            conn.execute(delete(strategies).where(strategies.c.id == strategy_id))

    def save_backtest(self, name: str, result: dict, strategy_id: int | None = None,
                      version: int | None = None) -> int:
        if not isinstance(result, dict) or not {"metadata", "metrics", "equity", "strategy_snapshot", "trades"}.issubset(result):
            raise ValueError("Only complete backtest results may be saved")
        label = str(name).strip()
        if not 1 <= len(label) <= 100:
            raise ValueError("Backtest label must contain 1–100 characters")
        config = parse_strategy(result["strategy_snapshot"])
        payload = json.dumps(result, allow_nan=False, sort_keys=True)
        if len(payload) > 8_000_000:
            raise ValueError("Backtest exceeds the 8 MB local storage limit")
        with self.db.engine.begin() as conn:
            if strategy_id is not None:
                valid = conn.execute(select(versions.c.version).where(
                    versions.c.strategy_id == strategy_id,
                    versions.c.version == version,
                )).scalar_one_or_none()
                if valid is None:
                    raise ValueError("Selected strategy/version no longer exists")
            record = conn.execute(insert(backtests).values(
                name=label, strategy_id=strategy_id, strategy_version=version,
                data_signature=str(result["metadata"]["data_sha256"]),
                result_json=payload, created_at=utc_now(),
            ))
            return int(record.inserted_primary_key[0])

    def list_backtests(self) -> list[dict]:
        with self.db.engine.connect() as conn:
            records = conn.execute(select(
                backtests.c.id, backtests.c.name, backtests.c.created_at,
                backtests.c.strategy_id, backtests.c.strategy_version,
            ).order_by(backtests.c.id.desc())).mappings()
            return [dict(row) for row in records]

    def load_backtest(self, backtest_id: int) -> dict:
        with self.db.engine.connect() as conn:
            record = conn.execute(select(backtests).where(
                backtests.c.id == backtest_id)).mappings().first()
        if record is None:
            raise ValueError("Backtest not found")
        result = json.loads(record["result_json"])
        return {"id": backtest_id, "name": record["name"], "saved_at": record["created_at"],
                "result": result}

    def delete_backtest(self, backtest_id: int) -> None:
        with self.db.engine.begin() as conn:
            conn.execute(delete(backtests).where(backtests.c.id == backtest_id))


def compare_results(saved: list[dict]) -> tuple[pd.DataFrame, list[str]]:
    """Compare saved metric summaries and call out materially different setups."""
    if not saved:
        return pd.DataFrame(), []
    rows = []
    for item in saved:
        r = item["result"]
        m, meta = r["metrics"], r["metadata"]
        rows.append({
            "Run": item["name"] + " (#" + str(item["id"]) + ")",
            "Strategy": r["strategy_snapshot"]["name"], "Symbol": meta["symbol"],
            "From": meta["from"], "To": meta["to"], "Interval": meta["timeframe"],
            "Data sha256": meta["data_sha256"][:12],
            "Provider": meta["provider"], "Adjustment": meta["adjustment_mode"],
            "Costs": json.dumps(meta["costs"], sort_keys=True),
            "Return %": m["total_return_pct"], "CAGR %": m["cagr_pct"],
            "Max drawdown %": m["max_drawdown_pct"], "Sharpe": m["sharpe"],
            "Sortino": m["sortino"], "Win rate %": m["win_rate_pct"],
            "Profit factor": m["profit_factor"], "Trades": m["trade_count"],
        })
    frame = pd.DataFrame(rows)
    warnings = []
    checks = {"Symbol": "Assets differ", "From": "Starting dates differ", "To": "Ending dates differ",
              "Interval": "Bar intervals differ", "Adjustment": "Price adjustment bases differ",
              "Costs": "Transaction cost assumptions differ", "Provider": "Data providers differ"}
    for key, label in checks.items():
        if frame[key].nunique(dropna=False) > 1:
            warnings.append(label + "; raw performance metrics are not directly comparable.")
    return frame, warnings
