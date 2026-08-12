"""add_content_digest_to_minute_sections

Add minute_sections.content_digest (LargeBinary 32, nullable) to store
HMAC-SHA256(plaintext, DEK) for encrypted sections. The server uses this
for stable fingerprinting of direction projections — the ciphertext changes
with every encryption (random GCM nonce) but the digest is deterministic
for identical plaintext.

Revision ID: 20260801_0004
Revises: 20260801_0003
Create Date: 2026-08-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260801_0004'
down_revision: Union[str, None] = '20260801_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(insp, table: str, column: str) -> bool:
    """Vérifie l'existence d'une colonne (Inspector.has_column n'existe pas
    dans toutes les versions de SQLAlchemy)."""
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    # Idempotent : une base fraîche créée par create_all a déjà content_digest
    if not _has_column(insp, "minute_sections", "content_digest"):
        op.add_column(
            'minute_sections',
            sa.Column('content_digest', sa.LargeBinary(32), nullable=True),
        )


def downgrade() -> None:
    # SQLite requires batch_alter_table for column drops.
    with op.batch_alter_table('minute_sections') as batch_op:
        batch_op.drop_column('content_digest')
