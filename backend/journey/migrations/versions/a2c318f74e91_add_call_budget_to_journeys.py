"""add_call_budget_to_journeys

Revision ID: a2c318f74e91
Revises: b1b405869802
Create Date: 2026-08-28 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2c318f74e91'
down_revision: Union[str, Sequence[str], None] = 'b1b405869802'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('journeys', sa.Column('call_budget', sa.Integer(), nullable=False, server_default='20'))


def downgrade() -> None:
    op.drop_column('journeys', 'call_budget')
