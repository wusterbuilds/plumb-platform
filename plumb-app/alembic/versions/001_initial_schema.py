"""Initial schema — users, deals, documents, extracted_values, cross_references, events

Revision ID: 001
Revises:
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="analyst"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Deals
    op.create_table(
        "deals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_type", sa.String(50), nullable=False, index=True),
        sa.Column("deal_subtype", sa.String(50)),
        sa.Column("capital_ask", sa.String(50)),
        sa.Column("status", sa.String(50), nullable=False, server_default="docs_received", index=True),
        sa.Column("previous_status", sa.String(50)),
        sa.Column("revision_number", sa.Integer(), server_default=sa.text("1")),
        sa.Column("property_address", sa.String(500)),
        sa.Column("property_type", sa.String(50)),
        sa.Column("sponsor", postgresql.JSON()),
        sa.Column("regulatory", postgresql.JSON()),
        sa.Column("typed_extension", postgresql.JSON()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("version", sa.Integer(), server_default=sa.text("1")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )

    # Documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("document_type", sa.String(50)),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("file_size", sa.BigInteger()),
        sa.Column("page_count", sa.Integer()),
        sa.Column("classification_confidence", sa.Float()),
        sa.Column("status", sa.String(50), nullable=False, server_default="uploaded"),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id")),
        sa.Column("uploaded_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )

    # Extracted values
    op.create_table(
        "extracted_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("field_name", sa.String(100), nullable=False, index=True),
        sa.Column("value", sa.Text()),
        sa.Column("source_doc_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id")),
        sa.Column("source_page", sa.Integer()),
        sa.Column("source_text_snippet", sa.Text()),
        sa.Column("confidence_score", sa.Float()),
        sa.Column("confidence_basis", postgresql.JSON()),
        sa.Column("extraction_method", sa.String(50)),
        sa.Column("prompt_version", sa.String(20)),
        sa.Column("flag", sa.String(10), nullable=False, server_default="red"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("override_value", sa.Text()),
        sa.Column("override_reason", sa.Text()),
        sa.Column("version", sa.Integer(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Cross references
    op.create_table(
        "cross_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("field_a", sa.String(100), nullable=False),
        sa.Column("field_a_value", sa.Text()),
        sa.Column("field_a_source_doc_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id")),
        sa.Column("field_b", sa.String(100), nullable=False),
        sa.Column("field_b_value", sa.Text()),
        sa.Column("field_b_source_doc_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id")),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("tolerance_applied", sa.String(20)),
        sa.Column("delta", sa.Text()),
        sa.Column("resolution", sa.String(20)),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Events (append-only audit log)
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("payload", postgresql.JSON()),
        sa.Column("revision_number", sa.Integer(), server_default=sa.text("1")),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("cross_references")
    op.drop_table("extracted_values")
    op.drop_table("documents")
    op.drop_table("deals")
    op.drop_table("users")
