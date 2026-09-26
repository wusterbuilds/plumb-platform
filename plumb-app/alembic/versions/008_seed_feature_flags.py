"""Seed default agent feature flags (enabled globally)

Revision ID: 008
Revises: 007
Create Date: 2026-04-10
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


AGENT_FLAGS = [
    "agent.deal_screening",
    "agent.extraction",
    "agent.research",
    "agent.underwriting",
    "agent.lender_targeting",
    "agent.om_writer",
    "agent.risk_report",
]


def upgrade() -> None:
    flags_tbl = sa.table(
        "feature_flags",
        sa.column("id", sa.UUID),
        sa.column("flag_name", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("enabled_deal_types", sa.JSON),
        sa.column("enabled_deal_ids", sa.JSON),
    )

    rows = [
        {
            "id": uuid.uuid4(),
            "flag_name": name,
            "enabled": True,
            "enabled_deal_types": [],
            "enabled_deal_ids": [],
        }
        for name in AGENT_FLAGS
    ]

    # Upsert-style: only insert flags that don't already exist.
    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT flag_name FROM feature_flags WHERE flag_name IN :names")
        .bindparams(sa.bindparam("names", AGENT_FLAGS, expanding=True))
    ).fetchall()
    existing_names = {row[0] for row in existing}

    new_rows = [r for r in rows if r["flag_name"] not in existing_names]
    if new_rows:
        op.bulk_insert(flags_tbl, new_rows)

    # Force-enable any flags that already existed but were disabled, so the
    # baseline pipeline is on out of the box.
    if existing_names:
        conn.execute(
            sa.text(
                "UPDATE feature_flags SET enabled = true WHERE flag_name IN :names"
            ).bindparams(sa.bindparam("names", list(existing_names), expanding=True))
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM feature_flags WHERE flag_name IN :names")
        .bindparams(sa.bindparam("names", AGENT_FLAGS, expanding=True))
    )
