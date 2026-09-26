"""Add property_name to deals table

Revision ID: 002
Revises: 001
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("property_name", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "property_name")
