"""notice_posts table

Revision ID: 20260801_0010
Revises: 20260801_0009
Create Date: 2026-08-19

Virtual notice board — Art. L.414-16: the delegation (and the designated
safety/health and equality delegates) may display communications on supports
accessible to staff, INCLUDING electronic ones.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260801_0010"
down_revision = "20260801_0009"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    if _has_table("notice_posts"):
        return
    op.create_table(
        "notice_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
    )
    op.create_index("ix_notice_posts_organization_id", "notice_posts", ["organization_id"])


def downgrade() -> None:
    if not _has_table("notice_posts"):
        return
    op.drop_index("ix_notice_posts_organization_id", table_name="notice_posts")
    op.drop_table("notice_posts")
