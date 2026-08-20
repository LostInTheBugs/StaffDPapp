"""users.is_first_mandate + safety_register_entries

Revision ID: 20260801_0013
Revises: 20260801_0012
Create Date: 2026-08-19

Congé-formation L.415-9 (primo-élus +16h) + registre sécurité/santé
L.414-14 (constatations contresignées par le chef de service).
Idempotente (gardes _has_column/_has_table) — create_all du démarrage
peut créer tables/colonnes AVANT la migration.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260801_0013"
down_revision = "20260801_0012"
branch_labels = None
depends_on = None


def _has_column(table: str, col: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(c["name"] == col for c in insp.get_columns(table))


def _has_table(name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return insp.has_table(name)


def upgrade() -> None:
    if not _has_column("users", "is_first_mandate"):
        op.add_column("users", sa.Column("is_first_mandate", sa.Boolean(), nullable=False, server_default=sa.false()))
    if not _has_table("safety_register_entries"):
        op.create_table(
            "safety_register_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("delegate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("entry_date", sa.Date(), nullable=False),
            sa.Column("location", sa.String(200), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("chef_service_name", sa.String(200), nullable=True),
            sa.Column("countersigned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_safety_register_org", "safety_register_entries", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_safety_register_org", table_name="safety_register_entries")
    op.drop_table("safety_register_entries")
    op.drop_column("users", "is_first_mandate")
