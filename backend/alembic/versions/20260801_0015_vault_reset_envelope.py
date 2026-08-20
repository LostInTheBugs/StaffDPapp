"""vault_keys.reset_envelope — enveloppe de reset démo

Revision ID: 20260801_0015
Revises: 20260801_0014
Create Date: 2026-08-20

Reset automatique de la démo (demande Fred 2026-08-20) : chaque matin, le
script scripts/reset_demo.py restaure l'enveloppe d'origine du coffre
(wrapped_dek + nonce + kdf_salt + kdf_params) → le mot de passe du coffre
redevient test123456 SANS perdre les PV (la DEK est identique, seule
l'enveloppe change). reset_envelope = JSON base64 de l'enveloppe capturée
au premier passage (état d'origine).
Idempotente (garde _has_column).
"""

import sqlalchemy as sa
from alembic import op

revision = "20260801_0015"
down_revision = "20260801_0014"
branch_labels = None
depends_on = None


def _has_column(table: str, col: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(c["name"] == col for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column("vault_keys", "reset_envelope"):
        op.add_column("vault_keys", sa.Column("reset_envelope", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("vault_keys", "reset_envelope")
