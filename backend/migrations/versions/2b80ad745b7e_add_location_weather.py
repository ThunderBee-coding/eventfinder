"""add_location_weather

Revision ID: 2b80ad745b7e
Revises: 003_app_settings
Create Date: 2026-05-31 19:15:34.450045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b80ad745b7e'
down_revision: Union[str, Sequence[str], None] = '003_app_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('events', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('events', sa.Column('bundesland', sa.String(10), nullable=True))
    op.create_table(
        'weather_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('lat_grid', sa.Float(), nullable=False),
        sa.Column('lon_grid', sa.Float(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('day', sa.Integer(), nullable=False),
        sa.Column('temp_max_median', sa.Float(), nullable=True),
        sa.Column('temp_min_median', sa.Float(), nullable=True),
        sa.Column('precip_median', sa.Float(), nullable=True),
        sa.Column('sample_years', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('lat_grid', 'lon_grid', 'month', 'day', name='uq_weather_grid_day'),
    )


def downgrade() -> None:
    op.drop_table('weather_history')
    op.drop_column('events', 'bundesland')
    op.drop_column('events', 'address')
