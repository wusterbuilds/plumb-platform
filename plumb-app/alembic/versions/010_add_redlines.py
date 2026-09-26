"""Add draft_redlines table and OMVersion redline/approval columns

Revision ID: 010
Revises: 009
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "draft_redlines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("artifact_type", sa.String(40), nullable=False),
        sa.Column("artifact_ref_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("section_key", sa.String(80), nullable=False, index=True),
        sa.Column("section_index", sa.Integer),
        sa.Column("original_text", sa.Text, nullable=False),
        sa.Column("edited_text", sa.Text, nullable=False),
        sa.Column("diff_hunks", JSON),
        sa.Column("rationale", sa.Text),
        sa.Column("correction_category", sa.String(40)),
        sa.Column("severity", sa.String(20), server_default="moderate"),
        sa.Column("archetype_signature", sa.String(120), index=True),
        sa.Column("reviewer_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reviewer_role", sa.String(40)),
        sa.Column("episode_id", UUID(as_uuid=True), sa.ForeignKey("episodes.id")),
        sa.Column("promoted_to_skill_id", UUID(as_uuid=True)),
        sa.Column("applied_in_version_id", UUID(as_uuid=True), index=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.add_column("om_versions", sa.Column("approval_status", sa.String(20)))
    op.add_column("om_versions", sa.Column("archetype_signature", sa.String(120)))
    op.add_column("om_versions", sa.Column("exemplar_eligible", sa.Boolean, server_default=sa.text("false")))
    op.add_column("om_versions", sa.Column("redline_count", sa.Integer, server_default="0"))
    op.add_column("om_versions", sa.Column("applied_episodes", JSON))
    op.create_index(
        "ix_om_versions_archetype_signature", "om_versions", ["archetype_signature"]
    )


def downgrade() -> None:
    op.drop_index("ix_om_versions_archetype_signature", table_name="om_versions")
    op.drop_column("om_versions", "applied_episodes")
    op.drop_column("om_versions", "redline_count")
    op.drop_column("om_versions", "exemplar_eligible")
    op.drop_column("om_versions", "archetype_signature")
    op.drop_column("om_versions", "approval_status")
    op.drop_table("draft_redlines")
