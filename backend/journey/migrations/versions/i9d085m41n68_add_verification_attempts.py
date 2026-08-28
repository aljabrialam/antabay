"""add_verification_attempts

Revision ID: i9d085m41n68
Revises: h8c974l30m57
Create Date: 2026-08-28 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i9d085m41n68'
down_revision: Union[str, Sequence[str], None] = 'h8c974l30m57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add verification_attempts table for post-action verification (012)."""
    op.create_table('verification_attempts',
    sa.Column('attempt_id', sa.String(), nullable=False),
    sa.Column('journey_id', sa.String(), nullable=False),
    sa.Column('action_type', sa.String(), nullable=False),
    sa.Column('affected_record_id', sa.String(), nullable=False),
    sa.Column('action_response_json', sa.Text(), nullable=True),
    sa.Column('queried_at', sa.String(), nullable=False),
    sa.Column('observed_at', sa.String(), nullable=False),
    sa.Column('query_result_json', sa.Text(), nullable=False),
    sa.Column('classification', sa.String(), nullable=False),
    sa.Column('condition_result', sa.String(), nullable=False),
    sa.Column('has_discrepancy', sa.Integer(), nullable=False),
    sa.Column('applied_to_state', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id'], ),
    sa.PrimaryKeyConstraint('attempt_id'),
    )


def downgrade() -> None:
    """Remove verification_attempts table."""
    op.drop_table('verification_attempts')
