"""create_search_records

Revision ID: c3d429g85f02
Revises: a2c318f74e91
Create Date: 2026-08-28 04:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d429g85f02'
down_revision: Union[str, Sequence[str], None] = 'a2c318f74e91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'search_records',
        sa.Column('search_id', sa.String(), nullable=False),
        sa.Column('journey_id', sa.String(), nullable=False),
        sa.Column('requested_at', sa.String(), nullable=False),
        sa.Column('responded_at', sa.String(), nullable=False),
        sa.Column('raw_response_json', sa.Text(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('atlas_status', sa.Integer(), nullable=False),
        sa.Column('option_count', sa.Integer(), nullable=False),
        sa.Column('budget_before', sa.Integer(), nullable=False),
        sa.Column('budget_after', sa.Integer(), nullable=False),
        sa.Column('outcome', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id']),
        sa.PrimaryKeyConstraint('search_id'),
    )


def downgrade() -> None:
    op.drop_table('search_records')
