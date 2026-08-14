"""delegate_activities table

Revision ID: 20260801_0009
Revises: 20260801_0008
Create Date: 2026-08-14

Activities logged by the designated delegates (sécurité/santé L.414-14,
égalité L.414-15).
"""

import sqlalchemy as sa

from alembic import op

revision = "20260801_0009"
down_revision = "20260801_0008"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    if _has_table("delegate_activities"):
        return
    op.create_table(
        "delegate_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("activity_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
    )
    op.create_index("ix_delegate_activities_organization_id", "delegate_activities", ["organization_id"])
    op.create_index("ix_delegate_activities_user_id", "delegate_activities", ["user_id"])


def downgrade() -> None:
    if _has_table("delegate_activities"):
        op.drop_table("delegate_activities")
