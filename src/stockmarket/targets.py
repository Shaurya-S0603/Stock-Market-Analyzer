from __future__ import annotations

import numpy as np
import pandas as pd

TARGET_COLUMNS = [
    "target_return",
    "target_net_return_long",
    "target_profitable_long",
    "target_direction",
    "target_magnitude",
    "target_action",
]


def build_forward_targets(close: pd.Series, horizon: int, round_trip_cost: float = 0.0) -> pd.DataFrame:
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    if round_trip_cost < 0:
        raise ValueError("round_trip_cost must be non-negative")
    close = pd.to_numeric(close, errors="coerce")
    future_return = close.shift(-horizon) / close - 1.0
    targets = pd.DataFrame(index=close.index)
    targets["target_return"] = future_return
    targets["target_net_return_long"] = future_return - round_trip_cost
    targets["target_profitable_long"] = (future_return > round_trip_cost).astype(float)
    targets["target_direction"] = np.sign(future_return)
    targets["target_magnitude"] = future_return.abs()
    targets["target_action"] = np.select(
        [future_return > round_trip_cost, future_return < -round_trip_cost],
        [1.0, -1.0],
        default=0.0,
    )
    targets.loc[future_return.isna(), [
        "target_profitable_long", "target_direction", "target_magnitude", "target_action"
    ]] = np.nan
    return targets
