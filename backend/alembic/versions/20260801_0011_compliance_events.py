"""compliance_events table

Revision ID: 20260801_0011
Revises: 20260801_0010
Create Date: 2026-08-19

Compliance cockpit events — plenary assemblies (L.415-7), eco-financial
reports (L.414-5), bureau names communication (L.416-1).
"""

import sqlalchemy as sa

from alembic import op

revision = "20260801_0011"
down_revision = "20260801_0010"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    if _has_table("compliance_events"):
        return
    op.create_table(
        "compliance_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
    )
    op.create_index("ix_compliance_events_organization_id", "compliance_events", ["organization_id"])


def downgrade() -> None:
    if not _has_table("compliance_events"):
        return
    op.drop_index("ix_compliance_events_organization_id", table_name="compliance_events")
    op.drop_table("compliance_events")
