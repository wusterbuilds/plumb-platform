"""Add tables for Sprints 1-5: metrics, skills, knowledge, lenders, developers,
deal outcomes, episodes, feature flags, golden examples

Revision ID: 005
Revises: 004
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # Sprint 1: Measurement
    # ---------------------------------------------------------------

    # Deal stage durations (velocity tracking)
    op.create_table(
        "deal_stage_durations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("stage_name", sa.String(50), nullable=False),
        sa.Column("entered_at", sa.DateTime, nullable=False),
        sa.Column("exited_at", sa.DateTime, nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("actor", sa.String(100), nullable=True),
        sa.Column("revision_number", sa.Integer, server_default=sa.text("1")),
    )

    # SLA alerts
    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("stage_name", sa.String(50), nullable=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("severity", sa.String(20), server_default="warning"),
        sa.Column("acknowledged", sa.Boolean, server_default=sa.text("false")),
        sa.Column("acknowledged_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ---------------------------------------------------------------
    # Sprint 2: Skills + Knowledge
    # ---------------------------------------------------------------

    op.create_table(
        "skills",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("skill_type", sa.String(50), nullable=False),
        sa.Column("target_prompt", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "skill_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("skill_id", UUID(as_uuid=True), sa.ForeignKey("skills.id"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("instructions", sa.Text, nullable=False),
        sa.Column("reference_examples", JSON, server_default=sa.text("'[]'::json")),
        sa.Column("validation_criteria", JSON, server_default=sa.text("'[]'::json")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("false")),
        sa.Column("regression_passed", sa.Boolean, nullable=True),
        sa.Column("regression_results", JSON, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "skill_test_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("skill_version_id", UUID(as_uuid=True), sa.ForeignKey("skill_versions.id"), nullable=False, index=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("results", JSON, nullable=True),
        sa.Column("overall_accuracy", sa.Float, nullable=True),
        sa.Column("improvement_delta", sa.Float, nullable=True),
        sa.Column("tested_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "knowledge_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entry_type", sa.String(50), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", JSON, server_default=sa.text("'[]'::json")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ---------------------------------------------------------------
    # Sprint 3: Client Memory + Lender Intelligence
    # ---------------------------------------------------------------

    op.create_table(
        "developers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("entity_structure", JSON, nullable=True),
        sa.Column("track_record", sa.Text, nullable=True),
        sa.Column("known_patterns", JSON, server_default=sa.text("'[]'::json")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("deal_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "developer_deals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("developer_id", UUID(as_uuid=True), sa.ForeignKey("developers.id"), nullable=False, index=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("role", sa.String(50), server_default="sponsor"),
        sa.UniqueConstraint("developer_id", "deal_id"),
    )

    op.create_table(
        "lenders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("lender_type", sa.String(50), nullable=False),
        sa.Column("general_preferences", JSON, nullable=True),
        sa.Column("credit_committee_notes", sa.Text, nullable=True),
        sa.Column("relationship_contacts", JSON, server_default=sa.text("'[]'::json")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "lender_appetite",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("lender_id", UUID(as_uuid=True), sa.ForeignKey("lenders.id"), nullable=False, index=True),
        sa.Column("property_types", JSON, server_default=sa.text("'[]'::json")),
        sa.Column("geographies", JSON, server_default=sa.text("'[]'::json")),
        sa.Column("deal_size_min", sa.Float, nullable=True),
        sa.Column("deal_size_max", sa.Float, nullable=True),
        sa.Column("ltc_max", sa.Float, nullable=True),
        sa.Column("rate_indication", sa.String(100), nullable=True),
        sa.Column("term_range", sa.String(100), nullable=True),
        sa.Column("recourse_preference", sa.String(50), nullable=True),
        sa.Column("appetite_signal", sa.String(50), server_default="active"),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("source_detail", sa.Text, nullable=True),
        sa.Column("recorded_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("is_stale", sa.Boolean, server_default=sa.text("false")),
    )

    op.create_table(
        "lender_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("lender_id", UUID(as_uuid=True), sa.ForeignKey("lenders.id"), nullable=False, index=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=True),
        sa.Column("property_type", sa.String(50), nullable=True),
        sa.Column("geography", sa.String(100), nullable=True),
        sa.Column("deal_size", sa.Float, nullable=True),
        sa.Column("ltc_quoted", sa.Float, nullable=True),
        sa.Column("rate_quoted", sa.String(100), nullable=True),
        sa.Column("term_quoted", sa.String(100), nullable=True),
        sa.Column("outcome", sa.String(50), nullable=True),
        sa.Column("pass_reason", sa.Text, nullable=True),
        sa.Column("closed_at", sa.DateTime, nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("recorded_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "deal_distributions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("lender_id", UUID(as_uuid=True), sa.ForeignKey("lenders.id"), nullable=False, index=True),
        sa.Column("distributed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("distributed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approach_angle", sa.Text, nullable=True),
    )

    op.create_table(
        "lender_responses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_distribution_id", UUID(as_uuid=True), sa.ForeignKey("deal_distributions.id"), nullable=False, index=True),
        sa.Column("response_type", sa.String(50), nullable=False),
        sa.Column("response_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("terms_offered", JSON, nullable=True),
        sa.Column("pass_reason", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )

    op.create_table(
        "deal_closings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, unique=True),
        sa.Column("winning_lender_id", UUID(as_uuid=True), sa.ForeignKey("lenders.id"), nullable=False),
        sa.Column("final_terms", JSON, nullable=True),
        sa.Column("closed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("total_turnaround_days", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )

    op.create_table(
        "episodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=True, index=True),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column("lesson", sa.Text, nullable=False),
        sa.Column("relevance_tags", JSON, server_default=sa.text("'[]'::json")),
        sa.Column("confidence", sa.String(20), server_default="tentative"),
        sa.Column("occurrence_count", sa.Integer, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ---------------------------------------------------------------
    # Sprint 4: Agent Harness
    # ---------------------------------------------------------------

    op.create_table(
        "feature_flags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("flag_name", sa.String(100), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("false")),
        sa.Column("enabled_deal_types", JSON, server_default=sa.text("'[]'::json")),
        sa.Column("enabled_deal_ids", JSON, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "golden_examples",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("example_type", sa.String(50), nullable=False),
        sa.Column("prompt_name", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(20), nullable=True),
        sa.Column("skill_version_id", UUID(as_uuid=True), sa.ForeignKey("skill_versions.id"), nullable=True),
        sa.Column("input_context", JSON, nullable=True),
        sa.Column("output", JSON, nullable=True),
        sa.Column("confirmed_value", JSON, nullable=True),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False, index=True),
        sa.Column("agent_name", sa.String(100), nullable=False, index=True),
        sa.Column("goal", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("iterations", sa.Integer, server_default=sa.text("0")),
        sa.Column("reasoning_trace", JSON, nullable=True),
        sa.Column("result", JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("input_tokens", sa.Integer, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer, server_default=sa.text("0")),
        sa.Column("cost_usd", sa.Float, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("feature_flag_used", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("golden_examples")
    op.drop_table("feature_flags")
    op.drop_table("episodes")
    op.drop_table("deal_closings")
    op.drop_table("lender_responses")
    op.drop_table("deal_distributions")
    op.drop_table("lender_transactions")
    op.drop_table("lender_appetite")
    op.drop_table("lenders")
    op.drop_table("developer_deals")
    op.drop_table("developers")
    op.drop_table("knowledge_entries")
    op.drop_table("skill_test_results")
    op.drop_table("skill_versions")
    op.drop_table("skills")
    op.drop_table("alerts")
    op.drop_table("deal_stage_durations")
