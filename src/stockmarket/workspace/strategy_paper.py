"""Isolated, opt-in, durable, long-only strategy paper simulation.

NEVER affects src/stockmarket/storage.py, AI Trader, or external brokerage.
Activation at latest completed bar prevents historical backfill trades.
Incremental cycles work through newly *completed* cached bars in timestamp order.
SQLite BEGIN IMMEDIATE serializes overlapping worker executions and commits
paper state plus fill journal atomically.
"""
from __future__ import annotations

import math
from hashlib import sha256

import pandas as pd
from sqlalchemy import Table, MetaData, Column, Integer, Float, String, Boolean, Text, select, update, insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .database import WorkspaceDB, schema_versions, utc_now
from .strategy_repository import StrategyRepository
from .strategy_schema import parse_strategy
from .strategy_signals import evaluate_strategy
from .strategy_backtest import validate_backtest_bars

meta = MetaData()
accounts = Table(
    "workspace_paper_strategies", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("label", String(100), nullable=False),
    Column("strategy_snapshot", Text, nullable=False),
    Column("strategy_id", Integer, nullable=False),
    Column("strategy_version", Integer, nullable=False),
    Column("symbol", String(40), nullable=False),
    Column("interval", String(10), nullable=False),
    Column("provider", String(80), nullable=False),
    Column("adjustment", String(32), nullable=False),
    Column("starting_cash", Float, nullable=False),
    Column("cash", Float, nullable=False),
    Column("shares", Integer, nullable=False),
    Column("cost_per_share", Float, nullable=False),
    Column("entry_fee", Float, nullable=False),
    Column("high_since_entry", Float, nullable=False),
    Column("entry_bar", String(48), nullable=True),
    Column("last_processed", String(48), nullable=False),
    Column("last_bar_hash", String(64), nullable=False),
    Column("last_close", Float, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("realized_pnl", Float, nullable=False),
    Column("created_at", String(48), nullable=False),
    Column("updated_at", String(48), nullable=False),
)
fills = Table(
    "workspace_paper_strategy_fills", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer, nullable=False),
    Column("bar_time", String(48), nullable=False),
    Column("side", String(4), nullable=False),
    Column("shares", Integer, nullable=False),
    Column("price", Float, nullable=False),
    Column("fee", Float, nullable=False),
    Column("realized_pnl", Float, nullable=False),
    Column("reason", String(80), nullable=False),
    Column("created_at", String(48), nullable=False),
)
decisions = Table(
    "workspace_paper_strategy_decisions", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer, nullable=False),
    Column("bar_time", String(48), nullable=False),
    Column("signal_time", String(48), nullable=False),
    Column("decision", String(25), nullable=False),
    Column("reason", String(140), nullable=False),
    Column("created_at", String(48), nullable=False),
)

def _stamp(ts) -> str:
    return pd.Timestamp(ts).tz_convert("UTC").isoformat()

def _bar_hash(row: pd.Series) -> str:
    return sha256("|".join(f"{float(row[k]):.12g}" for k in
                           ("open","high","low","close","volume")).encode("ascii")).hexdigest()

def _fee(quantity: int, price: float, costs) -> float:
    return costs.commission_fixed + quantity * price * costs.commission_pct / 100.

def _bars(db: WorkspaceDB, symbol: str, interval: str) -> pd.DataFrame:
    raw = db.load_candles(symbol, interval)
    if len(raw) < 3:
        raise ValueError("At least three cached candles required; download more history")
    validated = validate_backtest_bars(raw)
    return validated.iloc[:-1]  # last bar might be unfinished


class PaperStrategyRepository:
    def __init__(self, db: WorkspaceDB):
        self.db = db
        meta.create_all(db.engine)
        with db.engine.begin() as conn:
            conn.execute(sqlite_insert(schema_versions).values(
                version=5, applied_at=utc_now()).on_conflict_do_nothing())

    def create(self, strategy_id: int, *, starting_cash: float = 10000., label: str = "Strategy simulation") -> int:
        if not math.isfinite(starting_cash) or not 1 <= starting_cash <= 1e9:
            raise ValueError("Simulation starting cash must be between 1 and 1 billion")
        if not 1 <= len(label.strip()) <= 100:
            raise ValueError("Simulation label must be 1-100 characters")
        version = StrategyRepository(self.db).load(strategy_id)
        config = parse_strategy(version["definition"])
        completed = _bars(self.db, config.symbol, config.timeframe)
        if completed["provider"].nunique() != 1 or completed["adjustment_mode"].nunique() != 1:
            raise ValueError("Simulation cannot mix price providers or adjustment bases")
        row = completed.iloc[-1]
        with self.db.engine.begin() as conn:
            saved = conn.execute(insert(accounts).values(
                label=label.strip(), strategy_snapshot=config.model_dump_json(),
                strategy_id=strategy_id, strategy_version=version["version"],
                symbol=config.symbol, interval=config.timeframe,
                provider=str(row["provider"]), adjustment=str(row["adjustment_mode"]),
                starting_cash=starting_cash, cash=starting_cash, shares=0,
                cost_per_share=0, entry_fee=0, high_since_entry=0,
                entry_bar=None, last_processed=_stamp(completed.index[-1]),
                last_bar_hash=_bar_hash(row), last_close=float(row["close"]),
                enabled=False, realized_pnl=0, created_at=utc_now(), updated_at=utc_now()
            ))
            return int(saved.inserted_primary_key[0])

    def list_accounts(self) -> list[dict]:
        with self.db.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(accounts).order_by(accounts.c.id.desc())).mappings()]

    def list_fills(self, account_id: int, limit: int = 200) -> list[dict]:
        with self.db.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(fills).where(
                fills.c.account_id == account_id).order_by(fills.c.id.desc()).limit(limit)).mappings()]

    def list_decisions(self, account_id: int, limit: int = 200) -> list[dict]:
        with self.db.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(decisions).where(
                decisions.c.account_id == account_id).order_by(decisions.c.id.desc()).limit(limit)).mappings()]

    def set_enabled(self, account_id: int, enabled: bool) -> None:
        with self.db.engine.connect() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                current = conn.execute(select(accounts).where(accounts.c.id == account_id)).mappings().first()
                if current is None:
                    raise ValueError("Simulation not found")
                updates = {"enabled":bool(enabled), "updated_at":utc_now()}
                if enabled and not current["enabled"]:
                    # Resume starts at latest *confirmed* candle, never retro-trades idle history.
                    completed = _bars(self.db, current["symbol"], current["interval"])
                    if completed["provider"].nunique() != 1 or completed["adjustment_mode"].nunique() != 1:
                        raise ValueError("Mixed provider/adjustment history")
                    if (str(completed.iloc[-1]["provider"]), str(completed.iloc[-1]["adjustment_mode"])) != (current["provider"],current["adjustment"]):
                        raise ValueError("Provider/adjustment changed: create a new simulation")
                    updates |= {
                        "last_processed":_stamp(completed.index[-1]),
                        "last_bar_hash":_bar_hash(completed.iloc[-1]),
                        "last_close":float(completed.iloc[-1]["close"]),
                    }
                conn.execute(update(accounts).where(accounts.c.id == account_id).values(**updates))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def cycle(self, account_id: int) -> dict:
        """Transactionally apply unseen completed candles, no historical fills on activation."""
        with self.db.engine.connect() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                current = conn.execute(select(accounts).where(accounts.c.id == account_id)).mappings().first()
                if current is None:
                    raise ValueError("Simulation not found")
                if not current["enabled"]:
                    conn.commit()
                    return {"status":"disabled", "fills":0, "bars":0}
                cfg = parse_strategy(current["strategy_snapshot"])
                completed = _bars(self.db, current["symbol"], current["interval"])
                if completed["provider"].nunique() != 1 or completed["adjustment_mode"].nunique() != 1:
                    raise ValueError("Mixed provider/adjustment data cannot be simulated")
                if (str(completed.iloc[-1]["provider"]),str(completed.iloc[-1]["adjustment_mode"])) != (current["provider"], current["adjustment"]):
                    raise ValueError("Simulation price source changed; stop and create a new account")
                prior = completed.index[completed.index.map(_stamp) == current["last_processed"]]
                if len(prior) != 1:
                    raise ValueError("Checkpoint no longer in local historical data; disable this simulation")
                old_idx = completed.index.get_loc(prior[0])
                if _bar_hash(completed.iloc[old_idx]) != current["last_bar_hash"]:
                    raise ValueError("Historical bar at simulation checkpoint was revised; stop to prevent inconsistent fills")
                if old_idx >= len(completed)-1:
                    conn.commit()
                    return {"status":"unchanged","fills":0,"bars":0}
                signals = evaluate_strategy(completed, cfg)
                cash, qty = float(current["cash"]), int(current["shares"])
                cost, entry_fee = float(current["cost_per_share"]), float(current["entry_fee"])
                high = float(current["high_since_entry"])
                entry_bar = current["entry_bar"]
                realized = float(current["realized_pnl"])
                count = 0
                processed = 0

                def record(i: int, side: str, quantity: int, price: float, fee: float, pnl: float, reason: str):
                    nonlocal count
                    conn.execute(insert(fills).values(
                        account_id=account_id, bar_time=_stamp(completed.index[i]),
                        side=side, shares=quantity, price=price, fee=fee, realized_pnl=pnl,
                        reason=reason, created_at=utc_now()))
                    count += 1

                for i in range(old_idx+1, len(completed)):
                    row, prev = completed.iloc[i], completed.iloc[i-1]
                    open_price = float(row["open"])
                    processed += 1
                    reason = "hold"
                    decision = "HOLD"
                    if qty and bool(signals["exit"].iloc[i-1]):
                        sell_price = open_price * (1 - cfg.costs.slippage_pct/100)
                        fee = _fee(qty, sell_price, cfg.costs)
                        pnl = qty * (sell_price - cost) - entry_fee - fee
                        cash += qty*sell_price - fee
                        realized += pnl
                        record(i,"sell",qty,sell_price,fee,pnl,"signal_exit")
                        qty, cost, entry_fee, high, entry_bar = 0,0.,0.,0.,None
                        reason, decision = "closed on prior completed-bar exit signal","SELL"
                    elif not qty and bool(signals["entry"].iloc[i-1]):
                        buy_price = open_price * (1 + cfg.costs.slippage_pct/100)
                        equity = cash
                        if cfg.risk.sizing == "fixed_quantity":
                            requested = int(cfg.risk.value)
                        else:
                            budget = (cfg.risk.value/100 * equity if cfg.risk.sizing == "percent_of_equity" else cfg.risk.value)
                            requested = max(0, math.floor((budget - cfg.costs.commission_fixed) /
                                (buy_price*(1+cfg.costs.commission_pct/100))))
                        cap = min(cash,cfg.risk.max_exposure_pct/100 * equity)
                        max_shares = max(0, math.floor((cap-cfg.costs.commission_fixed)/
                                                      (buy_price*(1+cfg.costs.commission_pct/100))))
                        amount = min(requested,max_shares)
                        if amount:
                            fee = _fee(amount,buy_price,cfg.costs)
                            cash -= amount*buy_price+fee
                            qty,cost,entry_fee,high,entry_bar = amount,buy_price,fee,buy_price,_stamp(completed.index[i])
                            record(i,"buy",qty,buy_price,fee,0.,"signal_entry")
                            reason, decision = "filled using prior bar entry signal","BUY"
                        else:
                            reason,decision = "cash or exposure cap prevented entry","REJECT"

                    # Completed-bar protective stops, never use provisional newest bar.
                    if qty:
                        stop_levels = []
                        if cfg.risk.stop_loss_pct is not None:
                            stop_levels.append(cost*(1-cfg.risk.stop_loss_pct/100))
                        if cfg.risk.trailing_stop_pct is not None:
                            stop_levels.append(high*(1-cfg.risk.trailing_stop_pct/100))
                        stop = max(stop_levels) if stop_levels else None
                        target = cost*(1+cfg.risk.take_profit_pct/100) if cfg.risk.take_profit_pct is not None else None
                        if stop is not None and float(row["low"]) <= stop:
                            sell_price = min(open_price,stop)*(1-cfg.costs.slippage_pct/100)
                            fee = _fee(qty,sell_price,cfg.costs)
                            pnl = qty*(sell_price-cost)-entry_fee-fee
                            cash += qty*sell_price-fee
                            realized += pnl
                            record(i,"sell",qty,sell_price,fee,pnl,"protective_stop")
                            qty,cost,entry_fee,high,entry_bar = 0,0.,0.,0.,None
                            reason,decision = "protective stop on completed bar","SELL"
                        elif target is not None and float(row["high"]) >= target:
                            sell_price = max(open_price,target)*(1-cfg.costs.slippage_pct/100)
                            fee = _fee(qty,sell_price,cfg.costs)
                            pnl = qty*(sell_price-cost)-entry_fee-fee
                            cash += qty*sell_price-fee
                            realized += pnl
                            record(i,"sell",qty,sell_price,fee,pnl,"profit_target")
                            qty,cost,entry_fee,high,entry_bar = 0,0.,0.,0.,None
                            reason,decision = "profit target on completed bar","SELL"
                        else:
                            high = max(high,float(row["high"]))
                    if cash < -1e-6:
                        raise AssertionError("Simulated cash must never be negative")
                    conn.execute(insert(decisions).values(
                        account_id=account_id, bar_time=_stamp(completed.index[i]),
                        signal_time=_stamp(completed.index[i-1]),
                        decision=decision, reason=reason, created_at=utc_now()))
                last = completed.iloc[-1]
                conn.execute(update(accounts).where(accounts.c.id == account_id).values(
                    cash=max(0.,cash), shares=qty, cost_per_share=cost, entry_fee=entry_fee,
                    high_since_entry=high, entry_bar=entry_bar, realized_pnl=realized,
                    last_processed=_stamp(completed.index[-1]),
                    last_bar_hash=_bar_hash(last), last_close=float(last["close"]),
                    updated_at=utc_now())))
                conn.commit()
                return {"status":"executed","bars":processed,"fills":count}
            except Exception:
                conn.rollback()
                raise

    def cycle_all(self) -> list[dict]:
        outcomes = []
        for acct in self.list_accounts():
            if acct["enabled"]:
                outcomes.append({"account_id":acct["id"]} | self.cycle(acct["id"]))
        return outcomes

    def summary(self, account_id: int) -> dict:
        item = next((r for r in self.list_accounts() if r["id"] == account_id),None)
        if item is None:
            raise ValueError("Simulation not found")
        # Last *completed and processed* bar price; never call an external quote API.
        equity = float(item["cash"]) + int(item["shares"])*float(item["last_close"])
        return {"id":item["id"], "label":item["label"], "cash":float(item["cash"]),
                "shares":int(item["shares"]), "last_historical_close":float(item["last_close"]),
                "equity":equity, "unrealized_pnl":int(item["shares"])*(float(item["last_close"])-float(item["cost_per_share"]))-float(item["entry_fee"]),
                "realized_pnl":float(item["realized_pnl"]),
                "return_pct":(equity/float(item["starting_cash"])-1)*100,
                "enabled":bool(item["enabled"]), "last_processed":item["last_processed"],
                "symbol":item["symbol"], "interval":item["interval"],
                "strategy_version":item["strategy_version"], "provider":item["provider"]}
