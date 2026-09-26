"""Add market_data and public_data_cache tables, market_context column on deals

Revision ID: 003
Revises: 002
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_data",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("data_source", sa.String(50), nullable=False, index=True),
        sa.Column("data_type", sa.String(50), nullable=False, index=True),
        sa.Column("data", JSON, nullable=True),
        sa.Column("raw_data", sa.Text, nullable=True),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("source_doc_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("fetch_date", sa.DateTime, nullable=True),
        sa.Column("cache_expires_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "public_data_cache",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("cache_key", sa.String(500), nullable=False, unique=True, index=True),
        sa.Column("data_source", sa.String(50), nullable=False),
        sa.Column("raw_response", sa.Text, nullable=True),
        sa.Column("fetched_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=False),
    )

    op.add_column("deals", sa.Column("market_context", JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "market_context")
    op.drop_table("public_data_cache")
    op.drop_table("market_data")
