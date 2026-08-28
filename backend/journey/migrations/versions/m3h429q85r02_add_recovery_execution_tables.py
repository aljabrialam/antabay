"""add_recovery_execution_tables

Revision ID: m3h429q85r02
Revises: l2g318p74q91
Create Date: 2026-08-28 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm3h429q85r02'
down_revision: Union[str, Sequence[str], None] = 'l2g318p74q91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add recovery_executions and cancellation_attempts tables, and
    journeys.current_order_no column (011)."""
    op.add_column('journeys', sa.Column('current_order_no', sa.String(), nullable=True))

    op.create_table('recovery_executions',
    sa.Column('recovery_execution_id', sa.String(), nullable=False),
    sa.Column('recommendation_id', sa.String(), nullable=False),
    sa.Column('journey_id', sa.String(), nullable=False),
    sa.Column('started_at', sa.String(), nullable=False),
    sa.Column('concluded_at', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('abandonment_reason', sa.String(), nullable=True),
    sa.Column('superseded_order_no', sa.String(), nullable=True),
    sa.Column('replacement_order_no', sa.String(), nullable=True),
    sa.Column('replacement_outcome', sa.String(), nullable=True),
    sa.Column('cancellation_outcome', sa.String(), nullable=True),
    sa.Column('final_position_description', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id'], ),
    sa.PrimaryKeyConstraint('recovery_execution_id'),
    sa.UniqueConstraint('recommendation_id'),
    )
    op.create_table('cancellation_attempts',
    sa.Column('attempt_id', sa.String(), nullable=False),
    sa.Column('journey_id', sa.String(), nullable=False),
    sa.Column('order_no', sa.String(), nullable=False),
    sa.Column('requested_at', sa.String(), nullable=False),
    sa.Column('responded_at', sa.String(), nullable=True),
    sa.Column('raw_response_json', sa.Text(), nullable=True),
    sa.Column('outcome', sa.String(), nullable=False),
    sa.Column('reconciliation_raw_json', sa.Text(), nullable=True),
    sa.Column('confirmed_cancelled', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id'], ),
    sa.PrimaryKeyConstraint('attempt_id'),
    )


def downgrade() -> None:
    """Remove cancellation_attempts, recovery_executions, and current_order_no."""
    op.drop_table('cancellation_attempts')
    op.drop_table('recovery_executions')
    op.drop_column('journeys', 'current_order_no')
