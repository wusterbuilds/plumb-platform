"""Add deal_images and om_versions tables for Phase 3

Revision ID: 004
Revises: 003
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deal images table
    op.create_table(
        "deal_images",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("image_type", sa.String(50), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("caption", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
        sa.Column("associated_entity", sa.String(100), nullable=True),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime, server_default=sa.func.now()),
    )

    # OM versions table
    op.create_table(
        "om_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("html_s3_key", sa.String(500), nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("generated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("generated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("financial_model_snapshot", JSON, nullable=True),
        sa.Column("narrative_snapshot", JSON, nullable=True),
        sa.Column("status", sa.String(20), server_default="generating"),
        sa.UniqueConstraint("deal_id", "version_number"),
    )


def downgrade() -> None:
    op.drop_table("om_versions")
    op.drop_table("deal_images")
