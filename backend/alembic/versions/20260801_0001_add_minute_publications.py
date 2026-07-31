"""add_minute_publications

Revision ID: 20260801_0001
Revises: 521e941480fb
Create Date: 2026-08-01 00:00:00.000001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260801_0001'
down_revision: Union[str, None] = '521e941480fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('minute_publications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('minute_id', sa.Integer(), nullable=False),
        sa.Column('published_by_id', sa.Integer(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('pdf_sha256', sa.String(length=64), nullable=False),
        sa.Column('sections_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['minute_id'], ['minutes.id'], ),
        sa.ForeignKeyConstraint(['published_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_minute_publications_id'), 'minute_publications', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_minute_publications_id'), table_name='minute_publications')
    op.drop_table('minute_publications')
