"""vault_keys: recovery envelope columns

Revision ID: 20260801_0008
Revises: 20260801_0007
Create Date: 2026-08-14

Adds optional recovery-key envelope columns to vault_keys. The server only
stores the opaque envelope (wrapped DEK + nonce + PBKDF2 salt/params) — the
recovery key itself never leaves the client.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260801_0008"
down_revision = "20260801_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vault_keys", sa.Column("recovery_wrapped_dek", sa.LargeBinary(), nullable=True))
    op.add_column("vault_keys", sa.Column("recovery_nonce", sa.LargeBinary(), nullable=True))
    op.add_column("vault_keys", sa.Column("recovery_kdf_salt", sa.LargeBinary(), nullable=True))
    op.add_column("vault_keys", sa.Column("recovery_kdf_params", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("vault_keys", "recovery_kdf_params")
    op.drop_column("vault_keys", "recovery_kdf_salt")
    op.drop_column("vault_keys", "recovery_nonce")
    op.drop_column("vault_keys", "recovery_wrapped_dek")
