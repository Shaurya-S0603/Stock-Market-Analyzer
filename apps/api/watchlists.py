"""Authenticated watchlists: owner-scoped reads and writes, no trading operations."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.auth import OwnerId
from apps.api.cache import ThrottledOwner, cached_lists, remember_lists, invalidate_lists
from apps.api.storage import ResearchUser, SavedWatchlist, SavedSymbol, db_session
from stockmarket.workspace.database import clean_symbol

router = APIRouter(prefix="/api/v1/watchlists", tags=["Authenticated watchlists"])
Db = Annotated[Session, Depends(db_session)]

class NamePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=64)

class SymbolPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=40)

def normalized_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Watchlist name cannot be blank")
    return name

def normalized_symbol(value: str) -> str:
    try:
        return clean_symbol(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid ticker") from exc

def owned(db: Session, subject: str, list_id: UUID) -> SavedWatchlist:
    item = db.scalar(select(SavedWatchlist).where(
        SavedWatchlist.owner_id == subject, SavedWatchlist.id == str(list_id)
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return item

def safe_commit(db: Session):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate or conflicting saved research data") from exc

@router.get("")
def list_watchlists(subject: OwnerId, db: Db):
    cached = cached_lists(subject)
    if cached is not None:
        return cached
    rows = db.scalars(select(SavedWatchlist).where(
        SavedWatchlist.owner_id == subject
    ).order_by(SavedWatchlist.created_at, SavedWatchlist.id)).all()
    ids = [r.id for r in rows]
    symbols: dict[str, list[str]] = {list_id: [] for list_id in ids}
    if ids:
        items = db.execute(select(SavedSymbol.watchlist_id, SavedSymbol.symbol)
                           .where(SavedSymbol.watchlist_id.in_(ids))
                           .order_by(SavedSymbol.symbol)).all()
        for list_id, ticker in items:
            symbols[list_id].append(ticker)
    response = {"watchlists": [
        {"id": row.id, "name": row.name, "symbols": symbols[row.id],
         "created_at": row.created_at.isoformat()} for row in rows
    ]}
    remember_lists(subject, response)
    return response

@router.post("", status_code=201)
def create_watchlist(payload: NamePayload, subject: ThrottledOwner, db: Db):
    name = normalized_name(payload.name)
    count = db.scalar(select(func.count()).select_from(SavedWatchlist).where(
        SavedWatchlist.owner_id == subject
    ))
    if count >= 20:
        raise HTTPException(status_code=409, detail="Maximum of 20 watchlists per account")
    if db.get(ResearchUser, subject) is None:
        db.add(ResearchUser(id=subject))
        db.flush()
    list_item = SavedWatchlist(owner_id=subject, name=name)
    db.add(list_item)
    safe_commit(db)
    invalidate_lists(subject)
    return {"id": list_item.id, "name": name, "symbols": []}

@router.delete("/{list_id}", status_code=200)
def delete_watchlist(list_id: UUID, subject: ThrottledOwner, db: Db):
    row = owned(db, subject, list_id)
    db.delete(row)
    safe_commit(db)
    invalidate_lists(subject)
    return {"deleted": True}

@router.post("/{list_id}/symbols", status_code=201)
def add_symbol(list_id: UUID, payload: SymbolPayload, subject: ThrottledOwner, db: Db):
    owned(db, subject, list_id)
    ticker = normalized_symbol(payload.symbol)
    existing = db.scalar(select(SavedSymbol.id).where(
        SavedSymbol.watchlist_id == str(list_id), SavedSymbol.symbol == ticker))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Ticker already exists on this list")
    count = db.scalar(select(func.count()).select_from(SavedSymbol).where(
        SavedSymbol.watchlist_id == str(list_id)))
    if count >= 50:
        raise HTTPException(status_code=409, detail="Maximum of 50 symbols per watchlist")
    db.add(SavedSymbol(watchlist_id=str(list_id), symbol=ticker))
    safe_commit(db)
    invalidate_lists(subject)
    return {"symbol": ticker, "added": True}

@router.delete("/{list_id}/symbols/{symbol}")
def remove_symbol(list_id: UUID, symbol: str, subject: ThrottledOwner, db: Db):
    owned(db, subject, list_id)
    ticker = normalized_symbol(symbol)
    result = db.execute(delete(SavedSymbol).where(
        SavedSymbol.watchlist_id == str(list_id), SavedSymbol.symbol == ticker
    ))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Ticker not on watchlist")
    safe_commit(db)
    invalidate_lists(subject)
    return {"deleted": True}
