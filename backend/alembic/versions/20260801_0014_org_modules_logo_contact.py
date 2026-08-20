"""organizations: enabled_modules + logo + contact

Revision ID: 20260801_0014
Revises: 20260801_0013
Create Date: 2026-08-20

Personnalisation par organisation (demande Fred 2026-08-20) :
- enabled_modules : liste JSON des modules actifs (None = tous) ;
- logo_data : data URL de l'image (base64) affichée sur le login + nav ;
- contact_email / contact_phone / contact_hours : page contact DP.
Idempotente (gardes _has_column).
"""

import sqlalchemy as sa
from alembic import op

revision = "20260801_0014"
down_revision = "20260801_0013"
branch_labels = None
depends_on = None


def _has_column(table: str, col: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(c["name"] == col for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column("organizations", "enabled_modules"):
        op.add_column("organizations", sa.Column("enabled_modules", sa.Text(), nullable=True))
    if not _has_column("organizations", "logo_data"):
        op.add_column("organizations", sa.Column("logo_data", sa.Text(), nullable=True))
    if not _has_column("organizations", "contact_email"):
        op.add_column("organizations", sa.Column("contact_email", sa.String(300), nullable=True))
    if not _has_column("organizations", "contact_phone"):
        op.add_column("organizations", sa.Column("contact_phone", sa.String(100), nullable=True))
    if not _has_column("organizations", "contact_hours"):
        op.add_column("organizations", sa.Column("contact_hours", sa.Text(), nullable=True))


def downgrade() -> None:
    for col in ("enabled_modules", "logo_data", "contact_email", "contact_phone", "contact_hours"):
        op.drop_column("organizations", col)
