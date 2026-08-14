"""workforce_stats — L.414-3 semiannual workforce statistics by sex.

Revision ID: 20260801_0007
Revises: 20260801_0006
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa

revision = "20260801_0007"
down_revision = "20260801_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "workforce_stats" not in tables:
        op.create_table(
            "workforce_stats",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("organization_id", sa.Integer(), nullable=False, index=True),
            sa.Column("semester", sa.String(length=7), nullable=False),
            sa.Column("male_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("female_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.UniqueConstraint("organization_id", "semester", name="uq_workforce_stat_org_semester"),
        )
    else:
        # Idempotence : la table existe déjà (BDD fraîche créée via create_all)
        pass


def downgrade() -> None:
    op.drop_table("workforce_stats")
