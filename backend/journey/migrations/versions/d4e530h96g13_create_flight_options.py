"""create_flight_options

Revision ID: d4e530h96g13
Revises: c3d429g85f02
Create Date: 2026-08-28 04:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e530h96g13'
down_revision: Union[str, Sequence[str], None] = 'c3d429g85f02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flight_options',
        sa.Column('option_id', sa.String(), nullable=False),
        sa.Column('journey_id', sa.String(), nullable=False),
        sa.Column('search_record_id', sa.String(), nullable=False),
        sa.Column('fid', sa.String(), nullable=False),
        sa.Column('routing_identifier', sa.String(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('adult_price', sa.String(), nullable=False),
        sa.Column('adult_tax', sa.String(), nullable=False),
        sa.Column('transaction_fee', sa.String(), nullable=False),
        sa.Column('refreshed_at', sa.String(), nullable=True),
        sa.Column('expire_at', sa.String(), nullable=True),
        sa.Column('is_multi_leg', sa.Integer(), nullable=False),
        sa.Column('separate_bookings', sa.Integer(), nullable=False),
        sa.Column('recorded_at', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id']),
        sa.ForeignKeyConstraint(['search_record_id'], ['search_records.search_id']),
        sa.PrimaryKeyConstraint('option_id'),
    )


def downgrade() -> None:
    op.drop_table('flight_options')
