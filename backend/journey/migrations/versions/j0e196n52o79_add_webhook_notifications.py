"""add_webhook_notifications

Revision ID: j0e196n52o79
Revises: i9d085m41n68
Create Date: 2026-08-28 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j0e196n52o79'
down_revision: Union[str, Sequence[str], None] = 'i9d085m41n68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add webhook_notifications table for event reception (007)."""
    op.create_table('webhook_notifications',
    sa.Column('notification_id', sa.String(), nullable=False),
    sa.Column('received_at', sa.String(), nullable=False),
    sa.Column('declared_event_type', sa.String(), nullable=False),
    sa.Column('order_reference', sa.String(), nullable=True),
    sa.Column('raw_payload_json', sa.Text(), nullable=False),
    sa.Column('journey_id', sa.String(), nullable=True),
    sa.Column('associated', sa.Integer(), nullable=False),
    sa.Column('confirmation_triggered', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['journey_id'], ['journeys.journey_id'], ),
    sa.PrimaryKeyConstraint('notification_id'),
    )


def downgrade() -> None:
    """Remove webhook_notifications table."""
    op.drop_table('webhook_notifications')
