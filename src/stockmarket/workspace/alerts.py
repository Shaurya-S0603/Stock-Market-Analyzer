"""Persistent local alerts on newly completed historical bars.

No SMTP, SMS, brokerage, real-time-feed or cloud scheduler dependency.
The latest cached bar is treated as provisional. Activation checkpoints
the last completed bar so historic conditions cannot trigger instant alerts.
"""
from __future__ import annotations

import math
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import (
    Table, MetaData, Column, Integer, Float, String, Boolean, Text,
    UniqueConstraint, ForeignKey, select, update, delete, insert,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .database import WorkspaceDB, clean_symbol, schema_versions, utc_now
from .market_data import VALID_INTERVALS
from . import indicators
from .strategy_schema import parse_strategy
from .strategy_signals import evaluate_strategy
from .strategy_repository import StrategyRepository

AlertKind = Literal["price_cross", "rsi_cross", "sma_cross", "strategy_entry", "strategy_exit"]
Direction = Literal["above", "below"]

class AlertDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    symbol: str
    interval: Literal["1m", "5m", "15m", "1h", "1d", "1wk", "1mo"] = "1d"
    kind: AlertKind
    direction: Direction = "above"
    threshold: float = Field(default=100.0, ge=0, le=1e9)
    period: int = Field(default=14, ge=2, le=250)
    strategy_id: int | None = Field(default=None, ge=1)
    strategy_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def verify(self):
        self.symbol = clean_symbol(self.symbol)
        if not math.isfinite(self.threshold):
            raise ValueError("Threshold must be finite")
        if self.kind == "rsi_cross" and self.threshold > 100:
            raise ValueError("RSI thresholds must be within [0,100]")
        if self.kind in {"strategy_entry", "strategy_exit"}:
            if self.strategy_id is None or self.strategy_version is None:
                raise ValueError("Strategy alert needs pinned strategy ID and version")
        elif self.strategy_id is not None or self.strategy_version is not None:
            raise ValueError("Price/indicator alerts cannot reference a strategy")
        return self

meta = MetaData()
rules = Table(
    "workspace_alert_rules", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("label", String(100), nullable=False),
    Column("definition", Text, nullable=False),
    Column("last_processed", String(48), nullable=False),
    Column("enabled", Boolean, nullable=False, default=True),
    Column("created_at", String(48), nullable=False),
)
events = Table(
    "workspace_alert_events", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("alert_id", Integer, ForeignKey("workspace_alert_rules.id", ondelete="CASCADE"), nullable=False),
    Column("bar_time", String(48), nullable=False),
    Column("observed_close", Float, nullable=False),
    Column("description", Text, nullable=False),
    Column("created_at", String(48), nullable=False),
    UniqueConstraint("alert_id", "bar_time", name="uq_alert_observation"),
)

def _stamp(value) -> str:
    return pd.Timestamp(value).tz_convert("UTC").isoformat()

def _valid_history(db: WorkspaceDB, definition: AlertDefinition) -> pd.DataFrame:
    frame = db.load_candles(definition.symbol, definition.interval)
    if len(frame) < 3:
        return pd.DataFrame()
    # Pending/in-progress newest bar is excluded, even with delayed providers.
    completed = frame.iloc[:-1]
    if completed["adjustment_mode"].nunique() > 1 or completed["provider"].nunique() > 1:
        raise ValueError("Cannot mix data adjustment/provider modes for an alert")
    return completed

def _condition(frame: pd.DataFrame, definition: AlertDefinition, strategies: StrategyRepository) -> pd.Series:
    if definition.kind in {"strategy_entry", "strategy_exit"}:
        record = strategies.load(definition.strategy_id, definition.strategy_version)
        strategy = parse_strategy(record["definition"])
        if strategy.symbol != definition.symbol or strategy.timeframe != definition.interval:
            raise ValueError("Alert symbol/timeframe must match the pinned strategy version")
        column = "entry" if definition.kind == "strategy_entry" else "exit"
        return evaluate_strategy(frame, strategy)[column].fillna(False)
    close = frame["close"].astype(float)
    if definition.kind == "rsi_cross":
        value = indicators.rsi(frame, definition.period)
    elif definition.kind == "sma_cross":
        value = close / indicators.sma(frame, definition.period)
    else:
        value = close
    threshold = 1.0 if definition.kind == "sma_cross" else definition.threshold
    # Cross-only, never repeat a continuous condition every new bar.
    prev = value.shift(1)
    if definition.direction == "above":
        result = (value > threshold) & (prev <= threshold)
    else:
        result = (value < threshold) & (prev >= threshold)
    return result.fillna(False).astype(bool)

class AlertRepository:
    def __init__(self, db: WorkspaceDB):
        self.db = db
        meta.create_all(db.engine)
        with db.engine.begin() as conn:
            conn.execute(sqlite_insert(schema_versions).values(version=4, applied_at=utc_now()).on_conflict_do_nothing())

    def add(self, label: str, definition: AlertDefinition | dict) -> int:
        cfg = definition if isinstance(definition, AlertDefinition) else AlertDefinition.model_validate(definition)
        name = label.strip()
        if not 1 <= len(name) <= 100:
            raise ValueError("Alert name must contain 1-100 characters")
        if cfg.kind.startswith("strategy_"):
            obj = StrategyRepository(self.db).load(cfg.strategy_id, cfg.strategy_version)
            s = parse_strategy(obj["definition"])
            if (s.symbol, s.timeframe) != (cfg.symbol, cfg.interval):
                raise ValueError("Selected strategy must match alert symbol and interval")
        completed = _valid_history(self.db, cfg)
        if completed.empty:
            raise ValueError("Cache at least three historical bars before creating an alert")
        with self.db.engine.begin() as conn:
            result = conn.execute(insert(rules).values(
                label=name, definition=cfg.model_dump_json(), last_processed=_stamp(completed.index[-1]),
                enabled=True, created_at=utc_now()))
            return int(result.inserted_primary_key[0])

    def list_rules(self) -> list[dict]:
        with self.db.engine.connect() as conn:
            rows = conn.execute(select(rules).order_by(rules.c.id.desc())).mappings().all()
        return [dict(row) | {"definition": AlertDefinition.model_validate_json(row["definition"]).model_dump()} for row in rows]

    def list_events(self, limit: int = 300) -> list[dict]:
        with self.db.engine.connect() as conn:
            rows = conn.execute(select(events).order_by(events.c.id.desc()).limit(limit)).mappings().all()
        return [dict(row) for row in rows]

    def set_enabled(self, rule_id: int, enabled: bool) -> None:
        with self.db.engine.begin() as conn:
            record = conn.execute(select(rules).where(rules.c.id == rule_id)).mappings().first()
            if record is None:
                raise ValueError("Alert not found")
            cfg = AlertDefinition.model_validate_json(record["definition"])
            completed = _valid_history(self.db, cfg)
            checkpoint = _stamp(completed.index[-1]) if not completed.empty else record["last_processed"]
            # Re-enabling starts from current observed bar, not old missed alerts.
            conn.execute(update(rules).where(rules.c.id == rule_id).values(
                enabled=bool(enabled), last_processed=checkpoint if enabled else record["last_processed"]))

    def delete(self, rule_id: int) -> None:
        with self.db.engine.begin() as conn:
            conn.execute(delete(rules).where(rules.c.id == rule_id))

    def evaluate(self) -> dict:
        """Transactionally checkpoint and deduplicate. Concurrent workers serialize in SQLite."""
        total = 0
        examined = 0
        strategies = StrategyRepository(self.db)
        # IMMEDIATE acquires SQLite's single writer lock before reading checkpoints.
        with self.db.engine.connect() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                for row in conn.execute(select(rules).where(rules.c.enabled == True)).mappings().all():
                    cfg = AlertDefinition.model_validate_json(row["definition"])
                    completed = _valid_history(self.db, cfg)
                    if completed.empty or _stamp(completed.index[-1]) <= row["last_processed"]:
                        continue
                    condition = _condition(completed, cfg, strategies)
                    for ts in completed.index:
                        stamp = _stamp(ts)
                        if stamp <= row["last_processed"]:
                            continue
                        examined += 1
                        if bool(condition.loc[ts]):
                            message = f"{cfg.kind}: {cfg.symbol}, {cfg.interval}, {cfg.direction}"
                            saved = conn.execute(sqlite_insert(events).values(
                                alert_id=row["id"], bar_time=stamp,
                                observed_close=float(completed.loc[ts, "close"]),
                                description=message, created_at=utc_now(),
                            ).on_conflict_do_nothing())
                            total += saved.rowcount or 0
                    conn.execute(update(rules).where(rules.c.id == row["id"]).values(
                        last_processed=_stamp(completed.index[-1])))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {"new_events": total, "bars_examined": examined}
