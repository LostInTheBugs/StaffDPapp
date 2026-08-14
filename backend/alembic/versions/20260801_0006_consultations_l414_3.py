"""consultations_l414_3

Add the L.414-3 consultations tracking table (consultations). Idempotent:
fresh DBs created by create_all already have this table.

Revision ID: 20260801_0006
Revises: 20260801_0005
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260801_0006'
down_revision: Union[str, None] = '20260801_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if not insp.has_table("consultations"):
        op.create_table(
            'consultations',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('title', sa.String(300), nullable=False),
            sa.Column('category', sa.Enum(
                'conditions_travail', 'reglement_interieur', 'temps_travail',
                'pension', 'formation', 'reclassement', 'licenciements_collectifs',
                'transfert', 'interimaire', 'oeuvres_sociales', 'statistiques_sexe',
                'teletravail', 'autre',
                name='consultationcategory'), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('status', sa.Enum(
                'requested', 'response_received', 'closed',
                name='consultationstatus'), nullable=False, server_default='requested'),
            sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('response_due', sa.DateTime(timezone=True), nullable=True),
            sa.Column('direction_responded_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('direction_response', sa.Text(), nullable=True),
            sa.Column('last_reminded_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_consultations_id', 'consultations', ['id'])
        op.create_index('ix_consultations_organization_id', 'consultations', ['organization_id'])


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("consultations"):
        op.drop_table('consultations')
