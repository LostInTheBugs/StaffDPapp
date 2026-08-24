"""jwt_revocations + users.token_version — révocation JWT

Revision ID: 20260801_0017
Revises: 20260801_0016
Create Date: 2026-08-24

Révocation des jetons (ANALYSE-2026-08-24 §7) :
- `jwt_revocations` : logout ciblé d'un jeton précis (identifié par son
  claim `jti`, ajouté à l'émission) ;
- `users.token_version` : révocation de TOUS les jetons d'un compte
  (retrait de membre, compte compromis) — le JWT porte `ver`, toute
  différence est rejetée par get_current_user. Les jetons émis avant
  cette version (sans `ver`) sont traités comme ver=0 : une révocation
  les invalide, comportement voulu.

Idempotente (gardes _has_table/_has_column).
"""

import sqlalchemy as sa
from alembic import op

revision = "20260801_0017"
down_revision = "20260801_0016"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, col: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(c["name"] == col for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_table("jwt_revocations"):
        op.create_table(
            "jwt_revocations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("jti", sa.String(64), nullable=False, unique=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_jwt_revocations_jti", "jwt_revocations", ["jti"])
        op.create_index("ix_jwt_revocations_user_id", "jwt_revocations", ["user_id"])
    if not _has_column("users", "token_version"):
        op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    if _has_column("users", "token_version"):
        op.drop_column("users", "token_version")
    if _has_table("jwt_revocations"):
        op.drop_table("jwt_revocations")
