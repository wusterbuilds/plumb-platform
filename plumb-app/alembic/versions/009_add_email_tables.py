"""Add email_threads and email_messages tables for Gmail integration

Revision ID: 009
Revises: 008
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=True, index=True),
        sa.Column("gmail_thread_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("subject", sa.String(500)),
        sa.Column("sender_email", sa.String(255), nullable=False),
        sa.Column("sender_name", sa.String(255)),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "email_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", UUID(as_uuid=True), sa.ForeignKey("email_threads.id"), nullable=False, index=True),
        sa.Column("gmail_message_id", sa.String(100), unique=True, nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("from_email", sa.String(255)),
        sa.Column("from_name", sa.String(255)),
        sa.Column("body_text", sa.Text),
        sa.Column("body_html", sa.Text),
        sa.Column("attachments", JSON),
        sa.Column("sent_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("email_messages")
    op.drop_table("email_threads")
