"""Strict, provenance-preserving OHLCV CSV interchange for local market history."""
from __future__ import annotations

import csv
from io import BytesIO, StringIO
import re

import pandas as pd

from .database import WorkspaceDB, clean_symbol
from .market_data import VALID_INTERVALS, validate_history

MAX_CSV_BYTES = 15 * 1024 * 1024
MAX_CSV_BARS = 20000
REQUIRED = ["timestamp", "open", "high", "low", "close", "volume"]
METADATA = ["provider", "adjustment_mode"]
TZ_SUFFIX = re.compile(r"(Z|[+-]\d{2}:\d{2})$", re.IGNORECASE)


def export_history_csv(db: WorkspaceDB, symbol: str, interval: str) -> bytes:
    frame = db.load_candles(symbol, interval)
    if frame.empty:
        raise ValueError("No cached OHLCV bars to export")
    report = frame.loc[:, [col for col in REQUIRED[1:] + METADATA if col in frame.columns]].copy()
    report.insert(0, "timestamp", frame.index.strftime("%Y-%m-%dT%H:%M:%S%z"))
    return report.to_csv(index=False, float_format="%.12g").encode("utf-8")


def import_history_csv(db: WorkspaceDB, content: bytes, *, symbol: str,
                       interval: str) -> dict:
    clean = clean_symbol(symbol)
    if interval not in VALID_INTERVALS:
        raise ValueError("Unsupported historical interval")
    if not isinstance(content, bytes) or not content or len(content) > MAX_CSV_BYTES:
        raise ValueError("CSV is empty or exceeds the 15 MB limit")
    try:
        source = content.decode("utf-8-sig")
        header = next(csv.reader(StringIO(source)))
        if len(header) != len(set(header)):
            raise ValueError("CSV has duplicated column headers")
        if any(field not in header for field in REQUIRED):
            raise ValueError("CSV needs timestamp, open, high, low, close and volume")
        if any(column not in (REQUIRED + METADATA) for column in header):
            raise ValueError("CSV includes an unsupported column")
        table = pd.read_csv(BytesIO(content), encoding="utf-8-sig",
                            low_memory=False, nrows=MAX_CSV_BARS + 1)
        if table.empty or len(table) > MAX_CSV_BARS:
            raise ValueError("CSV contains no bars or exceeds 20,000 bars")
        timestamps = table["timestamp"].astype(str).str.strip()
        if not timestamps.map(lambda s: bool(TZ_SUFFIX.search(s))).all():
            raise ValueError("Every timestamp requires an explicit UTC offset or Z")
        idx = pd.to_datetime(timestamps, utc=True, errors="raise")
        frame = table.set_index(idx).drop(columns=["timestamp"])
        # Explicit metadata from exported QuantEdge CSV is retained.
        if "provider" in frame:
            provider_values = frame.pop("provider").dropna().unique()
            if len(provider_values) != 1 or not isinstance(provider_values[0], str):
                raise ValueError("CSV must contain one valid provider")
            provider = provider_values[0]
        else:
            provider = "local-csv-import"
        if "adjustment_mode" in frame:
            adjustment_values = frame.pop("adjustment_mode").dropna().unique()
            if len(adjustment_values) != 1 or adjustment_values[0] not in ("raw", "adjusted"):
                raise ValueError("Unsupported or mixed CSV adjustment modes")
            adjustment = adjustment_values[0]
        else:
            adjustment = "raw"
        if not provider.strip() or len(provider) > 80:
            raise ValueError("CSV provider name invalid")
        normalized = validate_history(frame, interval)
        existing = db.load_candles(clean, interval)
        if not existing.empty:
            overlap = existing.index.intersection(normalized.index)
            if len(overlap):
                rows = existing.loc[overlap]
                if any(rows["provider"] != provider) or any(rows["adjustment_mode"] != adjustment):
                    raise ValueError("Import would overwrite observations from a different provider or price basis")
        count = db.save_candles(clean, interval, normalized, provider=provider,
                                adjustment_mode=adjustment)
        return {"symbol": clean, "interval": interval, "bars_imported": count,
                "provider": provider, "adjustment_mode": adjustment,
                "from": normalized.index[0].isoformat(), "to": normalized.index[-1].isoformat()}
    except (UnicodeDecodeError, pd.errors.ParserError, KeyError) as exc:
        raise ValueError("CSV could not be parsed as valid OHLCV data") from exc
