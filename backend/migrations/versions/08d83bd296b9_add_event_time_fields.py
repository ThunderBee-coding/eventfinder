"""add_event_time_fields

Revision ID: 08d83bd296b9
Revises: 3ebe823d130a
Create Date: 2026-06-06 16:05:54.387402

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08d83bd296b9'
down_revision: Union[str, Sequence[str], None] = '3ebe823d130a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('events', sa.Column('event_start_time', sa.String(5), nullable=True))
    op.add_column('events', sa.Column('event_end_time', sa.String(5), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('events', 'event_end_time')
    op.drop_column('events', 'event_start_time')
