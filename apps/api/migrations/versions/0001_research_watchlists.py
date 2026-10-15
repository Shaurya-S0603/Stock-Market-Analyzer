"""Initial authenticated user-owned research watchlist schema.

Revision ID: qe_v3_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "qe_v3_0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("qe_users",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("qe_watchlists",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("owner_id", sa.String(length=100),
                  sa.ForeignKey("qe_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "name", name="uq_qe_owner_list_name"))
    op.create_index("ix_qe_watchlists_owner_id", "qe_watchlists", ["owner_id"])
    op.create_table("qe_watchlist_symbols",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("watchlist_id", sa.String(length=36),
                  sa.ForeignKey("qe_watchlists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("watchlist_id", "symbol", name="uq_qe_list_symbol"))
    op.create_index("ix_qe_watchlist_symbols_watchlist_id", "qe_watchlist_symbols", ["watchlist_id"])

def downgrade():
    op.drop_index("ix_qe_watchlist_symbols_watchlist_id", table_name="qe_watchlist_symbols")
    op.drop_table("qe_watchlist_symbols")
    op.drop_index("ix_qe_watchlists_owner_id", table_name="qe_watchlists")
    op.drop_table("qe_watchlists")
    op.drop_table("qe_users")
