"""auth hardening: verrouillage TOTP + expiration des invitations

Revision ID: 4b6d8e9f0a1c
Revises: 1f40476853f5
Create Date: 2026-08-12 16:00:00.000000

Ajoute :
- users.totp_failed_attempts / users.totp_locked_until (anti brute-force TOTP)
- invitations.expires_at (expiration 30 jours, backfill sur les existantes)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b6d8e9f0a1c'
down_revision: Union[str, None] = '1f40476853f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(insp, table: str, column: str) -> bool:
    """Vérifie l'existence d'une colonne (Inspector.has_column n'existe pas
    dans toutes les versions de SQLAlchemy)."""
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # Idempotent : une base fraîche créée par create_all a déjà ces colonnes
    if not _has_column(insp, "users", "totp_failed_attempts"):
        op.add_column('users', sa.Column('totp_failed_attempts', sa.Integer(), nullable=True))
    if not _has_column(insp, "users", "totp_locked_until"):
        op.add_column('users', sa.Column('totp_locked_until', sa.DateTime(timezone=True), nullable=True))
    if not _has_column(insp, "invitations", "expires_at"):
        op.add_column('invitations', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))

        # Rétro-compatibilité : les invitations existantes expirent 30 jours après leur création
        conn.execute(
            sa.text(
                "UPDATE invitations SET expires_at = datetime(created_at, '+30 days') "
                "WHERE expires_at IS NULL AND created_at IS NOT NULL"
            )
        )


def downgrade() -> None:
    op.drop_column('invitations', 'expires_at')
    op.drop_column('users', 'totp_locked_until')
    op.drop_column('users', 'totp_failed_attempts')
