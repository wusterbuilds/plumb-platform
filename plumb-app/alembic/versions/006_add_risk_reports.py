"""Add risk_reports table for versioned Risk Assessment Report PDFs

Revision ID: 006
Revises: 005
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("html_s3_key", sa.String(500), nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("overall_risk_rating", sa.String(20), nullable=True),
        sa.Column("risk_summary", sa.Text, nullable=True),
        sa.Column("findings_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("findings_snapshot", JSON, nullable=True),
        sa.Column("generated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("generated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="ready"),
        sa.UniqueConstraint("deal_id", "version_number", name="uq_risk_reports_deal_version"),
    )


def downgrade() -> None:
    op.drop_table("risk_reports")
