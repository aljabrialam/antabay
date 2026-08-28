"""add_booking_tables

Revision ID: h8c974l30m57
Revises: g7b863k29l46
Create Date: 2026-08-28 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h8c974l30m57'
down_revision: Union[str, Sequence[str], None] = 'g7b863k29l46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add orders, payments, and ticketing_queries tables for order creation and payment (005)."""
    op.create_table('orders',
    sa.Column('order_id', sa.String(), nullable=False),
    sa.Column('journey_id', sa.String(), nullable=False),
    sa.Column('option_id', sa.String(), nullable=False),
    sa.Column('requested_at', sa.String(), nullable=False),
    sa.Column('responded_at', sa.String(), nullable=True),
    sa.Column('raw_response_json', sa.Text(), nullable=True),
    sa.Column('outcome', sa.String(), nullable=False),
    sa.Column('order_no', sa.String(), nullable=True),
    sa.Column('booking_reference', sa.String(), nullable=True),
    sa.Column('ticketing_deadline', sa.String(), nullable=True),
    sa.Column('session_id_used', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id'], ),
    sa.ForeignKeyConstraint(['option_id'], ['flight_options.option_id'], ),
    sa.PrimaryKeyConstraint('order_id'),
    )
    op.create_table('payments',
    sa.Column('payment_id', sa.String(), nullable=False),
    sa.Column('journey_id', sa.String(), nullable=False),
    sa.Column('order_no', sa.String(), nullable=False),
    sa.Column('requested_at', sa.String(), nullable=False),
    sa.Column('responded_at', sa.String(), nullable=True),
    sa.Column('raw_response_json', sa.Text(), nullable=True),
    sa.Column('outcome', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id'], ),
    sa.PrimaryKeyConstraint('payment_id'),
    )
    op.create_table('ticketing_queries',
    sa.Column('query_id', sa.String(), nullable=False),
    sa.Column('journey_id', sa.String(), nullable=False),
    sa.Column('order_no', sa.String(), nullable=False),
    sa.Column('queried_at', sa.String(), nullable=False),
    sa.Column('raw_response_json', sa.Text(), nullable=False),
    sa.Column('order_status', sa.String(), nullable=True),
    sa.Column('ticket_status', sa.String(), nullable=True),
    sa.Column('passenger_ticket_numbers_json', sa.Text(), nullable=False),
    sa.Column('confirmed', sa.Integer(), nullable=False),
    sa.Column('is_terminal_error', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id'], ),
    sa.PrimaryKeyConstraint('query_id'),
    )


def downgrade() -> None:
    """Remove orders, payments, and ticketing_queries tables."""
    op.drop_table('ticketing_queries')
    op.drop_table('payments')
    op.drop_table('orders')
