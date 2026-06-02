"""add background image fields

Revision ID: 004_background_image
Revises: 2b80ad745b7e
Create Date: 2026-06-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_background_image'
down_revision: Union[str, Sequence[str], None] = '2b80ad745b7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('events', sa.Column('background_image_path', sa.String(255), nullable=True))
    op.add_column('events', sa.Column('background_blur', sa.SmallInteger(), nullable=False, server_default='4'))
    op.add_column('events', sa.Column('background_overlay', sa.Float(), nullable=False, server_default='0.55'))


def downgrade() -> None:
    op.drop_column('events', 'background_overlay')
    op.drop_column('events', 'background_blur')
    op.drop_column('events', 'background_image_path')
