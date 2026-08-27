"""create_legs

Revision ID: e5f641i07h24
Revises: d4e530h96g13
Create Date: 2026-08-28 04:03:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f641i07h24'
down_revision: Union[str, Sequence[str], None] = 'd4e530h96g13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'legs',
        sa.Column('leg_id', sa.String(), nullable=False),
        sa.Column('option_id', sa.String(), nullable=False),
        sa.Column('segment_index', sa.Integer(), nullable=False),
        sa.Column('carrier', sa.String(), nullable=False),
        sa.Column('flight_number', sa.String(), nullable=False),
        sa.Column('dep_airport', sa.String(), nullable=False),
        sa.Column('dep_time', sa.String(), nullable=False),
        sa.Column('arr_airport', sa.String(), nullable=False),
        sa.Column('arr_time', sa.String(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('stop_cities', sa.String(), nullable=False),
        sa.Column('cabin_class', sa.String(), nullable=False),
        sa.Column('seat_count', sa.Integer(), nullable=False),
        sa.Column('risk_sellout', sa.Integer(), nullable=False),
        sa.Column('code_share', sa.Integer(), nullable=False),
        sa.Column('aircraft_code', sa.String(), nullable=False),
        sa.Column('fare_family', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['option_id'], ['flight_options.option_id']),
        sa.PrimaryKeyConstraint('leg_id'),
    )


def downgrade() -> None:
    op.drop_table('legs')
