"""add_calendar_token

Revision ID: 3ebe823d130a
Revises: 004_background_image
Create Date: 2026-06-06 16:05:46.612228

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ebe823d130a'
down_revision: Union[str, Sequence[str], None] = '004_background_image'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('calendar_token', sa.String(64), nullable=True))
    op.create_unique_constraint('uq_users_calendar_token', 'users', ['calendar_token'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_users_calendar_token', 'users', type_='unique')
    op.drop_column('users', 'calendar_token')
