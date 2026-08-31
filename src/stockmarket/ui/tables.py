from __future__ import annotations

import pandas as pd

from ..services import SymbolAnalysis
from ..trading import PaperPortfolio


def signal_table(available: dict[str, SymbolAnalysis]) -> pd.DataFrame:
    rows = []
    for symbol, state in available.items():
        signal = state.signal
        rows.append({"symbol":symbol,"price":state.price,"signal":f"{signal.action} ({signal.confidence:.0%})","predicted_return_pct":signal.predicted_return*100.0,"net_edge_pct":signal.net_edge*100.0,"confidence":signal.confidence,"as_of":state.timestamp})
    return pd.DataFrame(rows).sort_values("symbol") if rows else pd.DataFrame()


def model_table(available: dict[str, SymbolAnalysis]) -> pd.DataFrame:
    rows = [{"symbol":symbol, **state.model.metrics} for symbol, state in available.items()]
    return pd.DataFrame(rows).sort_values("symbol") if rows else pd.DataFrame()


def positions_table(portfolio: PaperPortfolio, prices: dict[str, float]) -> pd.DataFrame:
    frame = pd.DataFrame(portfolio.positions_snapshot(prices))
    if frame.empty: return frame
    return frame.rename(columns={"symbol":"Symbol","quantity":"Qty","avg_cost":"Avg Cost","market_price":"Mark","market_value":"Market Value","cost_basis":"Cost Basis","unrealized_pnl":"Unrealized PnL","unrealized_pct":"Unrealized %","realized_pnl":"Realized PnL"})


def orders_table(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty: return frame
    for column, default in {"realized_pnl":0.0,"reason":"manual"}.items():
        if column not in frame.columns: frame[column] = default
    return frame.rename(columns={"symbol":"Symbol","side":"Side","quantity":"Qty","price":"Fill Price","fee":"Fee","realized_pnl":"Realized PnL","reason":"Reason","created_at":"Time"})[["Time","Symbol","Side","Qty","Fill Price","Fee","Realized PnL","Reason"]]
