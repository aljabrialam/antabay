"""add_simulated_to_webhook_notifications

Revision ID: k1f207o63p80
Revises: j0e196n52o79
Create Date: 2026-08-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k1f207o63p80'
down_revision: Union[str, Sequence[str], None] = 'j0e196n52o79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add simulated column to webhook_notifications (008)."""
    op.add_column(
        'webhook_notifications',
        sa.Column('simulated', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    """Remove simulated column from webhook_notifications."""
    op.drop_column('webhook_notifications', 'simulated')
