"""add_verifications

Revision ID: g7b863k29l46
Revises: f6a752j18i35
Create Date: 2026-08-28 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g7b863k29l46'
down_revision: Union[str, Sequence[str], None] = 'f6a752j18i35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add verifications table for price verification and offer staleness (004)."""
    op.create_table('verifications',
    sa.Column('verification_id', sa.String(), nullable=False),
    sa.Column('journey_id', sa.String(), nullable=False),
    sa.Column('option_id', sa.String(), nullable=False),
    sa.Column('requested_at', sa.String(), nullable=False),
    sa.Column('responded_at', sa.String(), nullable=False),
    sa.Column('raw_response_json', sa.Text(), nullable=False),
    sa.Column('status_code', sa.Integer(), nullable=False),
    sa.Column('atlas_status', sa.Integer(), nullable=True),
    sa.Column('outcome', sa.String(), nullable=False),
    sa.Column('session_id', sa.String(), nullable=True),
    sa.Column('max_seats', sa.Integer(), nullable=True),
    sa.Column('price_change_json', sa.Text(), nullable=True),
    sa.Column('passenger_requirements_json', sa.Text(), nullable=False),
    sa.Column('budget_before', sa.Integer(), nullable=False),
    sa.Column('budget_after', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id'], ),
    sa.ForeignKeyConstraint(['option_id'], ['flight_options.option_id'], ),
    sa.PrimaryKeyConstraint('verification_id'),
    )


def downgrade() -> None:
    """Remove verifications table."""
    op.drop_table('verifications')
