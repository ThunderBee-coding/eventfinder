"""Add app_settings table

Revision ID: 003_app_settings
Revises: 002_event_theming
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = '003_app_settings'
down_revision = '002_event_theming'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('is_encrypted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('app_settings')
