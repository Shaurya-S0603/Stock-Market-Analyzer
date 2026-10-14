"""Screen only a known, locally cached symbol universe. Missing data never passes."""
from __future__ import annotations

import math
import pandas as pd

from .database import WorkspaceDB, clean_symbol
from .indicators import indicator_snapshot, sma
from .research_storage import validate_screener


def screen_cached(db: WorkspaceDB, universe: list[str], configuration: dict) -> pd.DataFrame:
    config = validate_screener(configuration)
    filters = config["filters"]
    rows = []
    for raw in dict.fromkeys(universe):
        symbol = clean_symbol(raw)
        bars = db.load_candles(symbol, "1d")
        if bars.empty or len(bars) < 2:
            continue
        end = bars.iloc[-1]
        previous = bars.iloc[-2]
        close = float(end["close"])
        change_pct = (close / float(previous["close"]) - 1) * 100
        volume = float(end["volume"])
        reference_sma = None
        n = int(filters.get("above_sma", filters.get("below_sma", 20)))
        if len(bars) >= n:
            reference_sma = float(sma(bars, n).iloc[-1])
        snapshot = indicator_snapshot(bars)
        rsi_value = snapshot["rsi"]
        data = {
            "Symbol": symbol, "Saved close": close, "Change %": change_pct,
            "Volume": volume, "RSI": rsi_value, "SMA": reference_sma,
            "Observed at": str(bars.index[-1]), "Provider": str(end["provider"]),
        }
        lookup = {"min_price": close, "max_price": close, "min_volume": volume,
                  "min_change_pct": change_pct, "max_change_pct": change_pct,
                  "rsi_min": rsi_value, "rsi_max": rsi_value}
        accepted = True
        for key, threshold in filters.items():
            if key in {"above_sma", "below_sma"}:
                if reference_sma is None or not math.isfinite(reference_sma):
                    accepted = False
                    break
                if key == "above_sma" and not close > reference_sma:
                    accepted = False
                if key == "below_sma" and not close < reference_sma:
                    accepted = False
            elif lookup.get(key) is None:
                accepted = False
            elif key.startswith(("min_", "rsi_min")) and lookup[key] < threshold:
                accepted = False
            elif key.startswith(("max_", "rsi_max")) and lookup[key] > threshold:
                accepted = False
            if not accepted:
                break
        if accepted:
            rows.append(data)
    columns = ["Symbol", "Saved close", "Change %", "Volume", "RSI", "SMA", "Observed at", "Provider"]
    return pd.DataFrame(rows, columns=columns).sort_values("Symbol").reset_index(drop=True)
