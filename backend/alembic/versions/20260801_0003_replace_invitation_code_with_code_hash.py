"""replace_invitation_code_with_code_hash

Replace invitations.code (plaintext, ~41 bits, brute-forcable) with
invitations.code_hash (Argon2id hash, never reveals the code).

Revision ID: 20260801_0003
Revises: 20260801_0002
Create Date: 2026-08-01

Strategy for existing invitations:
  - INVITATIONS WITH A CLEARTEXT CODE: hash it with Argon2id and store.
    This is the normal case — existing invitations from before this
    migration have codes in the old `code` column.

  - INVITATIONS WHERE THE CODE IS ALREADY MISSING OR UNHASHABLE:
    Mark them as `is_used = True` so they cannot be exploited. This
    should never happen in practice (the column was NOT NULL), but
    we handle it defensively rather than crashing the migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '20260801_0003'
down_revision: Union[str, None] = '20260801_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add code_hash column (nullable initially to backfill)
    op.add_column(
        'invitations',
        sa.Column('code_hash', sa.String(255), nullable=True),
    )

    # 2. Backfill: hash existing plaintext codes.
    # We do this in raw SQL to avoid importing the app's security module
    # (which has side-effects), but we need Argon2id. Use a Python function
    # via the Alembic connection's execute.
    conn = op.get_bind()

    # Import argon2 inline so the migration doesn't depend on app-level imports
    from argon2 import PasswordHasher, Type
    ph = PasswordHasher(
        time_cost=3,
        memory_cost=65536,
        parallelism=1,
        hash_len=32,
        type=Type.ID,
    )

    # Fetch rows that still have a code in the old column
    result = conn.execute(
        text("SELECT id, code FROM invitations WHERE code IS NOT NULL")
    ).fetchall()

    hashed_count = 0
    invalidated_count = 0

    for row in result:
        inv_id, code = row
        if code and code.strip():
            try:
                code_hash = ph.hash(code.strip())
                conn.execute(
                    text("UPDATE invitations SET code_hash = :h WHERE id = :i"),
                    {"h": code_hash, "i": inv_id},
                )
                hashed_count += 1
            except Exception:
                # Code exists but cannot be hashed — mark invitation as used
                # so the dangling row cannot be exploited.
                conn.execute(
                    text(
                        "UPDATE invitations SET is_used = 1, "
                        "code_hash = 'MIGRATION_INVALID' WHERE id = :i"
                    ),
                    {"i": inv_id},
                )
                invalidated_count += 1
        else:
            # Empty/null code (shouldn't happen — column was NOT NULL) —
            # mark as used.
            conn.execute(
                text(
                    "UPDATE invitations SET is_used = 1, "
                    "code_hash = 'MIGRATION_INVALID' WHERE id = :i"
                ),
                {"i": inv_id},
            )
            invalidated_count += 1

    print(
        f"  Invitation code migration: {hashed_count} hashed, "
        f"{invalidated_count} invalidated"
    )

    # 3. Now that all rows have code_hash, make it NOT NULL
    with op.batch_alter_table('invitations') as batch_op:
        batch_op.alter_column('code_hash', nullable=False)

    # 4. Drop the old code column and its index.
    # In SQLite, we cannot drop a column with ALTER...DROP COLUMN easily
    # in older versions, but the batch_alter_table handles this for us.
    with op.batch_alter_table('invitations') as batch_op:
        batch_op.drop_index('ix_invitations_code')
        batch_op.drop_column('code')


def downgrade() -> None:
    # Re-add the code column
    with op.batch_alter_table('invitations') as batch_op:
        batch_op.add_column(
            sa.Column('code', sa.String(20), nullable=True)
        )
        batch_op.create_index(
            'ix_invitations_code', ['code'], unique=True
        )

    # Mark all invitations as used since we cannot recover the code from hash
    conn = op.get_bind()
    conn.execute(
        text("UPDATE invitations SET is_used = 1, code = 'DOWNGRADE_LOST'")
    )

    # Make code NOT NULL
    with op.batch_alter_table('invitations') as batch_op:
        batch_op.alter_column('code', nullable=False)
        batch_op.drop_column('code_hash')
