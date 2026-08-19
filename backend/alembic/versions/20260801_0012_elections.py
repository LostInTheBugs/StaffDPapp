"""elections tables (L.413-1 à L.413-6)

Revision ID: 20260801_0012
Revises: 20260801_0011
Create Date: 2026-08-19

Election cycle: elections, candidates (eligibility L.413-4), anonymous
ballots (identity) + votes (choice) split for unlinkable voting.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260801_0012"
down_revision = "20260801_0011"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    if not _has_table("elections"):
        op.create_table(
            "elections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("election_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("candidate_deadline", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.Enum("announced", "voting", "closed", name="electionstatus"), nullable=False),
            sa.Column("notes", sa.String(length=1000), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        )
        op.create_index("ix_elections_organization_id", "elections", ["organization_id"])
    if not _has_table("election_candidates"):
        op.create_table(
            "election_candidates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("election_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("full_name", sa.String(length=200), nullable=False),
            sa.Column("list_label", sa.String(length=200), nullable=False),
            sa.Column("birth_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("hire_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("declared_not_excluded", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["election_id"], ["elections.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        )
        op.create_index("ix_election_candidates_election_id", "election_candidates", ["election_id"])
    if not _has_table("election_ballots"):
        op.create_table(
            "election_ballots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("election_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("cast_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["election_id"], ["elections.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        )
        op.create_index("ix_election_ballots_election_id", "election_ballots", ["election_id"])
        op.create_index("ix_election_ballots_user_id", "election_ballots", ["user_id"])
    if not _has_table("election_votes"):
        op.create_table(
            "election_votes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("election_id", sa.Integer(), nullable=False),
            sa.Column("candidate_id", sa.Integer(), nullable=False),
            sa.Column("cast_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["election_id"], ["elections.id"]),
            sa.ForeignKeyConstraint(["candidate_id"], ["election_candidates.id"]),
        )
        op.create_index("ix_election_votes_election_id", "election_votes", ["election_id"])


def downgrade() -> None:
    for table in ("election_votes", "election_ballots", "election_candidates", "elections"):
        if _has_table(table):
            op.drop_table(table)
