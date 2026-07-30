"""lowercase all emails

Revision ID: 1f40476853f5
Revises: 31140e6e07a7
Create Date: 2026-07-30 21:47:00.000000

Normalises tous les emails en minuscules dans users et invitations.
Détecte les collisions AVANT de modifier quoi que ce soit.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f40476853f5'
down_revision: Union[str, None] = '31140e6e07a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _find_collisions(conn, table_name: str) -> list[str]:
    """Trouve les emails qui deviendraient des doublons après normalisation."""
    result = conn.execute(
        sa.text(
            f"SELECT LOWER(email) AS norm, COUNT(*) AS cnt, GROUP_CONCAT(email, ', ') AS originals "
            f"FROM {table_name} GROUP BY norm HAVING cnt > 1"
        )
    )
    collisions = []
    for row in result:
        collisions.append(f"  - {row.norm}: {row.cnt} occurrences ({row.originals})")
    return collisions


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Détection des collisions
    user_collisions = _find_collisions(conn, "users")
    inv_collisions = _find_collisions(conn, "invitations")

    all_collisions = user_collisions + inv_collisions
    if all_collisions:
        msg = (
            "\n\n╔══════════════════════════════════════════════════════╗\n"
            "║  ⛔ MIGRATION BLOQUÉE — emails en conflit détectés ║\n"
            "╚══════════════════════════════════════════════════════╝\n"
            "\n"
            "La normalisation en minuscules ne peut pas être appliquée\n"
            "car les emails suivants ne diffèrent QUE par la casse :\n\n"
        )
        if user_collisions:
            msg += "📧 Table users :\n" + "\n".join(user_collisions) + "\n\n"
        if inv_collisions:
            msg += "📧 Table invitations :\n" + "\n".join(inv_collisions) + "\n\n"
        msg += (
            "➡️  Résolvez les doublons manuellement (fusionnez ou supprimez\n"
            "    les comptes en double) avant de relancer la migration.\n\n"
        )
        raise Exception(msg)

    # 2. Normalisation
    conn.execute(sa.text("UPDATE users SET email = LOWER(email)"))
    conn.execute(sa.text("UPDATE invitations SET email = LOWER(email)"))


def downgrade() -> None:
    # Pas de downgrade : la normalisation est irréversible
    # (impossible de restaurer la casse originale)
    pass
