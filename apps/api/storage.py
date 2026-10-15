"""Minimal versioned owner-scoped research storage; does not touch Streamlit SQLite."""
from __future__ import annotations

from functools import lru_cache
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session

class Base(DeclarativeBase):
    pass

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

class ResearchUser(Base):
    __tablename__ = "qe_users"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

class SavedWatchlist(Base):
    __tablename__ = "qe_watchlists"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_qe_owner_list_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(100), ForeignKey("qe_users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    items: Mapped[list["SavedSymbol"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan", passive_deletes=True
    )

class SavedSymbol(Base):
    __tablename__ = "qe_watchlist_symbols"
    __table_args__ = (UniqueConstraint("watchlist_id", "symbol", name="uq_qe_list_symbol"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    watchlist_id: Mapped[str] = mapped_column(String(36), ForeignKey("qe_watchlists.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    watchlist: Mapped[SavedWatchlist] = relationship(back_populates="items")

@lru_cache(maxsize=4)
def _engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True, pool_recycle=1800)

def db_session():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="Research database not configured")
    if not (url.startswith("postgresql+") or url.startswith("postgresql://")
            or (os.getenv("QUANTEDGE_ALLOW_SQLITE_TEST_DB") == "1" and url.startswith("sqlite:"))):
        raise HTTPException(status_code=503, detail="Research database type not permitted")
    with Session(_engine(url)) as session:
        yield session
