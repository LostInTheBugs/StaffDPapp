"""election_votes → election_vote_tallies (anonymat structurel du scrutin)

Revision ID: 20260801_0016
Revises: 20260801_0015
Create Date: 2026-08-24

L'analyse de sécurité (ANALYSE-2026-08-24) a montré que election_ballots
(identité) et election_votes (choix) étaient écrits dans la MÊME
transaction, avec des id auto-incrémentés et des cast_at identiques :
le bulletin n°k correspond au vote n°k, la jointure est triviale par
ordre d'insertion. Pour un scrutin soumis au secret du vote (L.413-5),
c'est inacceptable.

La table election_votes est remplacée par election_vote_tallies : un
compteur agrégé par candidat, AUCUNE ligne par électeur → plus rien à
corréler, l'anonymat devient structurel. Les votes existants sont repliés
dans les compteurs (totaux préservés à l'identique), puis la table
fautive est supprimée — ces lignes SONT la fuite.

Idempotente (gardes _has_table). ⚠️ Sauvegarder la base avant d'appliquer
en production (drop de table intentionnel).
"""

import sqlalchemy as sa
from alembic import op

revision = "20260801_0016"
down_revision = "20260801_0015"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return insp.has_table(name)


def upgrade() -> None:
    if _has_table("election_vote_tallies"):
        return
    op.create_table(
        "election_vote_tallies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("election_id", sa.Integer(), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("election_candidates.id"), nullable=False, unique=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    )
    if _has_table("election_votes"):
        # Repli : totaux par candidat — les voix exprimées sont préservées à l'identique.
        op.execute(
            """
            INSERT INTO election_vote_tallies (election_id, candidate_id, count)
            SELECT election_id, candidate_id, COUNT(*)
            FROM election_votes
            GROUP BY election_id, candidate_id
            """
        )
        op.drop_table("election_votes")


def downgrade() -> None:
    if _has_table("election_votes"):
        return
    # Restaure une ligne par voix (ordre d'insertion non reconstructible —
    # l'horodatage d'origine est perdu, c'est le prix du correctif).
    op.create_table(
        "election_votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("election_id", sa.Integer(), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("election_candidates.id"), nullable=False),
        sa.Column("cast_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT election_id, candidate_id, count FROM election_vote_tallies")
    ).fetchall()
    for election_id, candidate_id, count in rows:
        for _ in range(count):
            bind.execute(
                sa.text(
                    "INSERT INTO election_votes (election_id, candidate_id) VALUES (:e, :c)"
                ),
                {"e": election_id, "c": candidate_id},
            )
    op.drop_table("election_vote_tallies")
