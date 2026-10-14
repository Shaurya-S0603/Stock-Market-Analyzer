"""Versioned SQLite JSON configuration store for Phase 2 chart layouts and screeners."""
from __future__ import annotations

import json

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, UniqueConstraint, insert, select, update, delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .database import WorkspaceDB, clean_symbol, schema_versions, utc_now
from .market_data import VALID_INTERVALS

metadata = MetaData()
research_items = Table(
    "workspace_research_items", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String(20), nullable=False),
    Column("name", String(100), nullable=False),
    Column("configuration", Text, nullable=False),
    Column("updated_at", String(40), nullable=False),
    UniqueConstraint("kind", "name", name="uq_research_kind_name"),
)

INDICATORS = {
    "SMA", "EMA", "WMA", "Bollinger", "Breakout", "VWAP",
    "RSI", "MACD", "ATR", "ROC", "Stochastic", "OBV",
}
CHART_TYPES = {"Candles", "OHLC", "Line", "Area"}
FILTERS = {
    "min_price", "max_price", "min_volume", "min_change_pct", "max_change_pct",
    "rsi_min", "rsi_max", "above_sma", "below_sma",
}


def validate_chart(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("Chart settings must be an object")
    if set(config) - {"version", "symbol", "interval", "chart_type", "indicators", "length", "rsi_length", "bollinger_std", "volume"}:
        raise ValueError("Unknown chart settings")
    if config.get("version", 1) != 1:
        raise ValueError("Unsupported chart schema version")
    symbol = clean_symbol(config.get("symbol", "MSFT"))
    interval = str(config.get("interval", "1d"))
    if interval not in VALID_INTERVALS:
        raise ValueError("Unsupported chart interval")
    chart_type = str(config.get("chart_type", "Candles"))
    if chart_type not in CHART_TYPES:
        raise ValueError("Unsupported chart type")
    indicators = config.get("indicators", ["SMA", "RSI"])
    if not isinstance(indicators, list) or len(indicators) > 12 or any(not isinstance(x, str) for x in indicators) or len(set(indicators)) != len(indicators) or any(x not in INDICATORS for x in indicators):
        raise ValueError("Unsupported or duplicated chart indicator")
    if "VWAP" in indicators and interval not in {"1m", "5m", "15m", "1h"}:
        raise ValueError("VWAP requires intraday market data")
    length = config.get("length", 20)
    rsi_length = config.get("rsi_length", 14)
    std = config.get("bollinger_std", 2.0)
    for value in (length, rsi_length):
        if isinstance(value, bool) or not isinstance(value, int) or not 2 <= value <= 250:
            raise ValueError("Indicator lengths must be integers from 2 to 250")
    if isinstance(std, bool) or not isinstance(std, (int, float)) or not 0 < std <= 10:
        raise ValueError("Bollinger deviation must be in (0, 10]")
    if not isinstance(config.get("volume", True), bool):
        raise ValueError("Volume visibility must be boolean")
    return {
        "version": 1, "symbol": symbol, "interval": interval, "chart_type": chart_type,
        "indicators": list(indicators), "length": length, "rsi_length": rsi_length,
        "bollinger_std": float(std), "volume": config.get("volume", True),
    }


def validate_screener(config: dict) -> dict:
    if not isinstance(config, dict) or set(config) - {"version", "filters"}:
        raise ValueError("Screener settings must be an object with filters")
    if config.get("version", 1) != 1:
        raise ValueError("Unsupported screener schema version")
    criteria = config.get("filters", {})
    if not isinstance(criteria, dict) or set(criteria) - FILTERS:
        raise ValueError("Unsupported screener filter")
    cleaned = {}
    for key, value in criteria.items():
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError(f"Filter {key} must be numeric")
        number = float(value)
        if not -1e12 <= number <= 1e12:
            raise ValueError("Filter values must be finite and within allowed bounds")
        if key in {"rsi_min", "rsi_max"} and not 0 <= number <= 100:
            raise ValueError("RSI thresholds must be between 0 and 100")
        if key in {"min_price", "max_price", "min_volume"} and number < 0:
            raise ValueError("Price and volume thresholds must be nonnegative")
        if key in {"above_sma", "below_sma"} and not 2 <= number <= 250 or (key in {"above_sma", "below_sma"} and not number.is_integer()):
            raise ValueError("Moving-average periods must be integers between 2 and 250")
        cleaned[key] = int(number) if key in {"above_sma", "below_sma"} else number
    for lo, hi in [("min_price", "max_price"), ("rsi_min", "rsi_max"), ("min_change_pct", "max_change_pct")]:
        if lo in cleaned and hi in cleaned and cleaned[lo] > cleaned[hi]:
            raise ValueError(f"{lo} cannot exceed {hi}")
    return {"version": 1, "filters": cleaned}


class ResearchRepository:
    """A table added without changing existing paper state or OHLCV records."""

    def __init__(self, db: WorkspaceDB):
        self.db = db
        metadata.create_all(self.db.engine)
        with self.db.engine.begin() as conn:
            conn.execute(sqlite_insert(schema_versions).values(
                version=2, applied_at=utc_now()
            ).on_conflict_do_nothing())

    def save(self, kind: str, name: str, configuration: dict, item_id: int | None = None) -> int:
        if kind not in {"chart", "screener"}:
            raise ValueError("Unknown research item")
        label = str(name).strip()
        if not 1 <= len(label) <= 100:
            raise ValueError("Name must be 1–100 characters")
        config = validate_chart(configuration) if kind == "chart" else validate_screener(configuration)
        payload = json.dumps(config, allow_nan=False, sort_keys=True)
        with self.db.engine.begin() as conn:
            if item_id is not None:
                matches = conn.execute(select(research_items.c.id).where(
                    research_items.c.id == item_id, research_items.c.kind == kind
                )).scalar_one_or_none()
                if matches is None:
                    raise ValueError("Saved item no longer exists")
                conflict = conn.execute(select(research_items.c.id).where(
                    research_items.c.kind == kind, research_items.c.name == label,
                    research_items.c.id != item_id
                )).scalar_one_or_none()
                if conflict is not None:
                    raise ValueError("A saved item already has that name")
                conn.execute(update(research_items).where(research_items.c.id == item_id).values(
                    name=label, configuration=payload, updated_at=utc_now()))
                return int(item_id)
            conflict = conn.execute(select(research_items.c.id).where(
                research_items.c.kind == kind, research_items.c.name == label,
            )).scalar_one_or_none()
            if conflict is not None:
                raise ValueError("A saved item already has that name")
            result = conn.execute(insert(research_items).values(
                kind=kind, name=label, configuration=payload, updated_at=utc_now()))
            return int(result.inserted_primary_key[0])

    def list(self, kind: str) -> list[dict]:
        if kind not in {"chart", "screener"}:
            raise ValueError("Unknown research item")
        with self.db.engine.connect() as conn:
            rows = conn.execute(select(research_items).where(
                research_items.c.kind == kind).order_by(research_items.c.name)
            ).mappings().all()
        return [{"id": row["id"], "name": row["name"], "configuration": json.loads(row["configuration"]),
                 "updated_at": row["updated_at"]} for row in rows]

    def delete(self, kind: str, item_id: int) -> None:
        if kind not in {"chart", "screener"}:
            raise ValueError("Unknown research item")
        with self.db.engine.begin() as conn:
            conn.execute(delete(research_items).where(
                research_items.c.kind == kind, research_items.c.id == item_id))
