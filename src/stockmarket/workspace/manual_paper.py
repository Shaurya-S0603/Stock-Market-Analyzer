"""Strictly local, manual, single-symbol paper portfolios.

Manual buys and sells use the LAST COMPLETED cached historical candle, never
an executable/live quote. Explicitly no brokerage API, borrowing, or shorting.
Every operation journals an auditable fill and changes cash atomically.
"""
from __future__ import annotations

import math
from sqlalchemy import Table, Column, Integer, Float, String, MetaData, ForeignKey, select, insert, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .database import WorkspaceDB, clean_symbol, schema_versions, utc_now

meta = MetaData()
accounts = Table("workspace_manual_accounts", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("symbol", String(40), nullable=False),
    Column("interval", String(10), nullable=False),
    Column("starting_cash", Float, nullable=False),
    Column("cash", Float, nullable=False),
    Column("shares", Integer, nullable=False),
    Column("average_entry", Float, nullable=False),
    Column("outstanding_entry_fees", Float, nullable=False),
    Column("realized_pnl", Float, nullable=False),
    Column("created_at", String(48), nullable=False),
)
orders = Table("workspace_manual_orders", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer, ForeignKey("workspace_manual_accounts.id", ondelete="CASCADE"), nullable=False),
    Column("timestamp", String(48), nullable=False),
    Column("observed_bar", String(48), nullable=False),
    Column("side", String(4), nullable=False),
    Column("shares", Integer, nullable=False),
    Column("price", Float, nullable=False),
    Column("commission", Float, nullable=False),
    Column("realized_pnl", Float, nullable=False),
    Column("created_at", String(48), nullable=False),
)

def _nonnegative_amount(value: float, label: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0 or number > 1_000_000:
        raise ValueError(f"{label} must be finite and between 0 and 1,000,000")
    return number

class ManualPaperRepository:
    def __init__(self, db: WorkspaceDB):
        self.db = db
        meta.create_all(db.engine)
        with db.engine.begin() as conn:
            conn.execute(sqlite_insert(schema_versions).values(
                version=6, applied_at=utc_now()).on_conflict_do_nothing())

    def _quote(self, symbol: str, interval: str) -> dict:
        frame = self.db.load_candles(symbol, interval)
        if len(frame) < 3:
            raise ValueError("At least three historical candles are needed for a completed-bar paper quote")
        prior = frame.iloc[-2]
        price = float(prior["close"])
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Cached quote is invalid")
        return {"close": price, "bar": frame.index[-2].isoformat(),
                "provider": str(prior["provider"]), "basis": str(prior["adjustment_mode"])}

    def create(self, name: str, symbol: str, starting_cash: float, interval: str = "1d") -> int:
        clean = clean_symbol(symbol)
        title = str(name).strip()
        if not 1 <= len(title) <= 100:
            raise ValueError("Portfolio name must contain 1–100 characters")
        cash = float(starting_cash)
        if not math.isfinite(cash) or not (1 <= cash <= 1e9):
            raise ValueError("Paper starting capital must be between 1 and 1 billion")
        if interval != "1d":
            raise ValueError("Manual portfolios currently use daily historical candles")
        self._quote(clean, interval)
        with self.db.engine.begin() as conn:
            row = conn.execute(insert(accounts).values(
                name=title, symbol=clean, interval=interval, starting_cash=cash,
                cash=cash, shares=0, average_entry=0., outstanding_entry_fees=0.,
                realized_pnl=0., created_at=utc_now()
            ))
            return int(row.inserted_primary_key[0])

    def list_accounts(self) -> list[dict]:
        with self.db.engine.connect() as conn:
            return [dict(row) for row in conn.execute(
                select(accounts).order_by(accounts.c.id.desc())).mappings()]

    def list_orders(self, account_id: int, limit: int = 300) -> list[dict]:
        with self.db.engine.connect() as conn:
            return [dict(row) for row in conn.execute(
                select(orders).where(orders.c.account_id == account_id)
                .order_by(orders.c.id.desc()).limit(limit)).mappings()]

    def summary(self, account_id: int) -> dict:
        item = next((a for a in self.list_accounts() if a["id"] == account_id), None)
        if item is None:
            raise ValueError("Manual portfolio not found")
        quote = self._quote(item["symbol"], item["interval"])
        equity = float(item["cash"]) + int(item["shares"]) * quote["close"]
        return {**item, "equity": equity, "last_completed_close": quote["close"],
                "last_completed_bar": quote["bar"], "price_provider": quote["provider"],
                "unrealized_pnl": (int(item["shares"]) * (quote["close"] - float(item["average_entry"]))
                                   - float(item["outstanding_entry_fees"])),
                "total_return_pct": (equity / float(item["starting_cash"]) - 1) * 100}

    def order(self, account_id: int, side: str, shares: int,
              *, commission_fixed: float = 0., commission_pct: float = 0.,
              slippage_pct: float = 0.) -> dict:
        if side not in {"buy", "sell"} or type(shares) is not int or shares < 1 or shares > 1_000_000:
            raise ValueError("Order requires BUY or SELL and a positive whole-share quantity")
        fixed = _nonnegative_amount(commission_fixed, "Fixed commission")
        rate = _nonnegative_amount(commission_pct, "Percentage commission")
        slip = _nonnegative_amount(slippage_pct, "Slippage")
        if rate > 10 or slip > 10:
            raise ValueError("Commission or slippage cannot exceed 10%")
        with self.db.engine.connect() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                item = conn.execute(select(accounts).where(
                    accounts.c.id == account_id)).mappings().first()
                if item is None:
                    raise ValueError("Manual portfolio not found")
                quote = self._quote(item["symbol"], item["interval"])
                price = quote["close"] * (1 + slip / 100 if side == "buy" else 1 - slip / 100)
                fee = fixed + shares * price * rate / 100
                cash = float(item["cash"])
                owned = int(item["shares"])
                avg = float(item["average_entry"])
                entry_fees = float(item["outstanding_entry_fees"])
                realized = float(item["realized_pnl"])
                trade_pnl = 0.
                if side == "buy":
                    cost = shares * price + fee
                    if cost > cash + 1e-8:
                        raise ValueError("Insufficient simulated cash, including modeled fees")
                    cash -= cost
                    avg = (avg * owned + price * shares) / (owned + shares)
                    owned += shares
                    entry_fees += fee
                else:
                    if shares > owned:
                        raise ValueError("Cannot sell more simulated shares than owned")
                    allocated_entry_fee = entry_fees * shares / owned
                    trade_pnl = shares * (price - avg) - fee - allocated_entry_fee
                    realized += trade_pnl
                    cash += shares * price - fee
                    owned -= shares
                    entry_fees -= allocated_entry_fee
                    if owned == 0:
                        avg = 0.
                        entry_fees = 0.
                if cash < -1e-8:
                    raise AssertionError("Negative simulated cash")
                conn.execute(update(accounts).where(accounts.c.id == account_id).values(
                    cash=max(0., cash), shares=owned, average_entry=avg,
                    outstanding_entry_fees=entry_fees, realized_pnl=realized,
                ))
                row = conn.execute(insert(orders).values(
                    account_id=account_id, timestamp=utc_now(),
                    observed_bar=quote["bar"], side=side, shares=shares,
                    price=price, commission=fee, realized_pnl=trade_pnl,
                    created_at=utc_now(),
                ))
                conn.commit()
                return {"order_id": int(row.inserted_primary_key[0]), "side": side,
                        "quantity": shares, "price": price, "fee": fee,
                        "cash": max(0., cash), "shares_held": owned,
                        "realized_pnl": trade_pnl, "observed_bar": quote["bar"],
                        "paper_only": True}
            except Exception:
                conn.rollback()
                raise
