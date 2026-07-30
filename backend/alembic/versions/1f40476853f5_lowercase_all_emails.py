"""Normalise tous les emails (strip + lowercase) dans users et invitations.

Revision ID: 1f40476853f5
Revises: 31140e6e07a7
Create Date: 2026-07-30 21:47:00.000000

Utilise exactement la même fonction normalize_email() que l'application
(app.core.security) pour garantir une cohérence parfaite.
Détecte les collisions sur users AVANT modification (invitations non
concernées : pas de contrainte d'unicité sur invitations.email).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.core.security import normalize_email


# revision identifiers, used by Alembic.
revision: str = '1f40476853f5'
down_revision: Union[str, None] = '31140e6e07a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _find_collisions(conn) -> list[str]:
    """Trouve les emails de la table users qui deviendraient des doublons
    après normalisation via normalize_email().

    Ne concerne QUE la table users, seule porteuse de la contrainte unique.
    Les invitations n'ont pas de contrainte d'unicité sur l'email.
    """
    rows = conn.execute(sa.text("SELECT id, email FROM users")).fetchall()

    groups: dict[str, list[str]] = {}
    for row in rows:
        norm = normalize_email(row.email)
        groups.setdefault(norm, []).append(row.email)

    collisions = []
    for norm, originals in groups.items():
        if len(originals) > 1:
            collisions.append(
                f"  - {norm}: {len(originals)} occurrences ({', '.join(originals)})"
            )
    return collisions


def _do_upgrade(conn) -> None:
    """Normalise les emails dans users et invitations avec normalize_email().

    - users : détection de collisions AVANT normalisation (bloque si trouvées).
    - invitations : normalisation sans contrôle préalable (pas d'unicité).
    - Seules les lignes dont l'email change sont modifiées (idempotent).
    """
    # 1. Détection des collisions sur users uniquement
    collisions = _find_collisions(conn)
    if collisions:
        msg = (
            "\n\n╔══════════════════════════════════════════════════════╗\n"
            "║  ⛔ MIGRATION BLOQUÉE — emails en conflit détectés ║\n"
            "╚══════════════════════════════════════════════════════╝\n"
            "\n"
            "La normalisation des emails ne peut pas être appliquée\n"
            "car les emails suivants de la table users ne diffèrent\n"
            "QUE par la casse ou les espaces :\n\n"
            "📧 Table users :\n" + "\n".join(collisions) + "\n\n"
            "➡️  Résolvez les doublons manuellement (fusionnez ou supprimez\n"
            "    les comptes en double) avant de relancer la migration.\n\n"
        )
        raise Exception(msg)

    # 2. Normalisation des users
    rows = conn.execute(sa.text("SELECT id, email FROM users")).fetchall()
    for row in rows:
        norm = normalize_email(row.email)
        if norm != row.email:
            conn.execute(
                sa.text("UPDATE users SET email = :email WHERE id = :id"),
                {"email": norm, "id": row.id},
            )

    # 3. Normalisation des invitations (sans détection de collision)
    rows = conn.execute(sa.text("SELECT id, email FROM invitations")).fetchall()
    for row in rows:
        norm = normalize_email(row.email)
        if norm != row.email:
            conn.execute(
                sa.text("UPDATE invitations SET email = :email WHERE id = :id"),
                {"email": norm, "id": row.id},
            )


def upgrade() -> None:
    conn = op.get_bind()
    _do_upgrade(conn)


def downgrade() -> None:
    # Pas de downgrade : la normalisation est irréversible
    # (impossible de restaurer la casse originale)
    pass
