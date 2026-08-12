"""add_vault_keys_and_pv_vault_enabled

Revision ID: 20260801_0002
Revises: 20260801_0001
Create Date: 2026-08-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260801_0002'
down_revision: Union[str, None] = '20260801_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add pv_vault_enabled to organizations
    op.add_column(
        'organizations',
        sa.Column('pv_vault_enabled', sa.Boolean(), nullable=False, server_default=sa.text('0')),
    )

    # Create vault_keys table with raw SQL to include CHECK constraint
    # (Alembic's create_table + CheckConstraint doesn't reliably emit the
    #  CHECK for SQLite, so we use raw SQL for the full DDL.)
    op.execute("""
        CREATE TABLE vault_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            user_id INTEGER,
            invitation_id INTEGER,
            wrapped_dek BLOB NOT NULL,
            nonce BLOB NOT NULL,
            kdf_salt BLOB NOT NULL,
            kdf_params TEXT NOT NULL,
            dek_version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (invitation_id) REFERENCES invitations(id),
            CHECK (
                (user_id IS NOT NULL AND invitation_id IS NULL) OR
                (user_id IS NULL AND invitation_id IS NOT NULL)
            )
        )
    """)
    # Index for the PK lookups
    op.create_index(op.f('ix_vault_keys_id'), 'vault_keys', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_vault_keys_id'), table_name='vault_keys')
    op.drop_table('vault_keys')
    op.drop_column('organizations', 'pv_vault_enabled')
