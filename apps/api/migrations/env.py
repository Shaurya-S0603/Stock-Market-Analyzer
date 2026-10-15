"""Run only the v3 research schema migrations; never touch v2 SQLite."""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from apps.api.storage import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be set before running migrations")
    if not (url.startswith("postgresql+") or url.startswith("postgresql://")
            or (os.getenv("QUANTEDGE_ALLOW_SQLITE_TEST_DB") == "1" and url.startswith("sqlite:"))):
        raise RuntimeError("Only PostgreSQL is supported outside isolated database tests")
    return url

def run_migrations_offline():
    context.configure(url=get_url(), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    engine = create_engine(get_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
