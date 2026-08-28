"""add_journey_events

Revision ID: f6a752j18i35
Revises: e5f641i07h24
Create Date: 2026-08-28 10:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a752j18i35'
down_revision: Union[str, Sequence[str], None] = 'e5f641i07h24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add journey_events table for the agent trace console (006)."""
    op.create_table('journey_events',
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('journey_id', sa.String(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(), nullable=False),
    sa.Column('payload_json', sa.Text(), nullable=False),
    sa.Column('simulated', sa.Integer(), nullable=False),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id'], ),
    sa.PrimaryKeyConstraint('event_id'),
    sa.UniqueConstraint('journey_id', 'sequence', name='uq_journey_events_journey_sequence')
    )


def downgrade() -> None:
    """Remove journey_events table."""
    op.drop_table('journey_events')
