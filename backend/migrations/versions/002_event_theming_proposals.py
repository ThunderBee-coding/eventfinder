"""Add event theming and date proposals

Revision ID: 002_event_theming
Revises: a4de437b52ec
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_event_theming'
down_revision = 'a4de437b52ec'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('events', sa.Column('accent_color', sa.String(7), nullable=False, server_default='#06b6d4'))
    op.add_column('events', sa.Column('cover_image_path', sa.String(255), nullable=True))

    op.create_table(
        'date_proposals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('proposed_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('event_id', 'proposed_date', name='uq_event_date_proposal'),
    )


def downgrade() -> None:
    op.drop_table('date_proposals')
    op.drop_column('events', 'cover_image_path')
    op.drop_column('events', 'accent_color')
