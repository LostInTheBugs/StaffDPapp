"""email_and_share_links

Add notification infrastructure (email_configs, email_outbox) and secure
minute share links (minute_share_links). All steps idempotent: fresh DBs
created by create_all already have these tables/columns.

Revision ID: 20260801_0005
Revises: 20260801_0004
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260801_0005'
down_revision: Union[str, None] = '20260801_0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(insp, table: str, column: str) -> bool:
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if not insp.has_table("email_configs"):
        op.create_table(
            'email_configs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False, unique=True),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('transport_mode', sa.Enum('eml', 'smtp', 'external', 'mailbox', name='transportmode'), nullable=False, server_default='eml'),
            sa.Column('from_name', sa.String(200), nullable=True),
            sa.Column('from_email', sa.String(300), nullable=True),
            sa.Column('reply_to', sa.String(300), nullable=True),
            sa.Column('signature', sa.Text(), nullable=True),
            sa.Column('smtp_host', sa.String(300), nullable=True),
            sa.Column('smtp_port', sa.Integer(), nullable=False, server_default='587'),
            sa.Column('smtp_user', sa.String(300), nullable=True),
            sa.Column('smtp_password', sa.String(500), nullable=True),
            sa.Column('smtp_use_tls', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('smtp_use_ssl', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('direction_email', sa.String(300), nullable=True),
            sa.Column('remind_days_before', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        )

    if insp.has_table("email_configs") and not _has_column(insp, "email_configs", "direction_email"):
        op.add_column("email_configs", sa.Column("direction_email", sa.String(300), nullable=True))

    if not insp.has_table("email_outbox"):
        op.create_table(
            'email_outbox',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
            sa.Column('event_type', sa.Enum('meeting_invite', 'meeting_reminder', 'minutes_direction', 'minutes_dp', 'member_invite', 'test', name='emaileventtype'), nullable=False),
            sa.Column('transport', sa.Enum('eml', 'smtp', 'external', 'mailbox', name='transportmode'), nullable=False),
            sa.Column('recipient_name', sa.String(300), nullable=True),
            sa.Column('recipient_email', sa.String(300), nullable=False),
            sa.Column('lang', sa.String(8), nullable=False, server_default='fr'),
            sa.Column('subject', sa.String(500), nullable=False),
            sa.Column('body_html', sa.Text(), nullable=False),
            sa.Column('body_text', sa.Text(), nullable=False),
            sa.Column('payload', sa.JSON(), nullable=True),
            sa.Column('status', sa.Enum('ready', 'sent', 'failed', 'cancelled', name='emailstatus'), nullable=False, server_default='ready'),
            sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('eml_path', sa.String(500), nullable=True),
            sa.Column('exported_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_email_outbox_organization_id', 'email_outbox', ['organization_id'])
        op.create_index('ix_email_outbox_status', 'email_outbox', ['status'])

    if not insp.has_table("minute_share_links"):
        op.create_table(
            'minute_share_links',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
            sa.Column('minute_id', sa.Integer(), sa.ForeignKey('minutes.id'), nullable=False),
            sa.Column('token', sa.String(64), nullable=False, unique=True),
            sa.Column('envelope', sa.Text(), nullable=False),
            sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_viewed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('revoked', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        )
        op.create_index('ix_minute_share_links_organization_id', 'minute_share_links', ['organization_id'])
        op.create_index('ix_minute_share_links_minute_id', 'minute_share_links', ['minute_id'])
        op.create_index('ix_minute_share_links_token', 'minute_share_links', ['token'], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("minute_share_links"):
        op.drop_table("minute_share_links")
    if insp.has_table("email_outbox"):
        op.drop_table("email_outbox")
    if insp.has_table("email_configs"):
        op.drop_table("email_configs")
