"""add_impact_evaluation_tables

Revision ID: l2g318p74q91
Revises: k1f207o63p80
Create Date: 2026-08-28 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l2g318p74q91'
down_revision: Union[str, Sequence[str], None] = 'k1f207o63p80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add impact_evaluations and recommendations tables (009)."""
    op.create_table('impact_evaluations',
    sa.Column('evaluation_id', sa.String(), nullable=False),
    sa.Column('journey_id', sa.String(), nullable=False),
    sa.Column('triggering_event_id', sa.String(), nullable=False),
    sa.Column('triggering_sequence', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.String(), nullable=False),
    sa.Column('concluded_at', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('objective_satisfied', sa.Integer(), nullable=True),
    sa.Column('violation_description', sa.Text(), nullable=True),
    sa.Column('violated_constraints_json', sa.Text(), nullable=True),
    sa.Column('violation_extent', sa.String(), nullable=True),
    sa.Column('recommendation_id', sa.String(), nullable=True),
    sa.Column('no_alternative_reason', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id'], ),
    sa.PrimaryKeyConstraint('evaluation_id'),
    )
    op.create_table('recommendations',
    sa.Column('recommendation_id', sa.String(), nullable=False),
    sa.Column('evaluation_id', sa.String(), nullable=False),
    sa.Column('option_id', sa.String(), nullable=False),
    sa.Column('verification_id', sa.String(), nullable=False),
    sa.Column('cost_relative_description', sa.String(), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=False),
    sa.Column('constraint_breach', sa.Integer(), nullable=False),
    sa.Column('constraint_breach_detail', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['evaluation_id'], ['impact_evaluations.evaluation_id'], ),
    sa.ForeignKeyConstraint(['option_id'], ['flight_options.option_id'], ),
    sa.ForeignKeyConstraint(['verification_id'], ['verifications.verification_id'], ),
    sa.PrimaryKeyConstraint('recommendation_id'),
    )


def downgrade() -> None:
    """Remove recommendations and impact_evaluations tables."""
    op.drop_table('recommendations')
    op.drop_table('impact_evaluations')
