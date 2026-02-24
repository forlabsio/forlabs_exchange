"""add bot fields: strategy_type, monthly_fee, sharpe_ratio

Revision ID: a1b2c3d4e5f6
Revises: 52e1f826084e
Create Date: 2026-02-24 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '52e1f826084e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bots', sa.Column('strategy_type', sa.String(length=20), nullable=True, server_default='alternating'))
    op.add_column('bots', sa.Column('monthly_fee', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'))
    op.add_column('bot_performance', sa.Column('sharpe_ratio', sa.Numeric(precision=8, scale=4), nullable=True, server_default='0'))


def downgrade() -> None:
    op.drop_column('bot_performance', 'sharpe_ratio')
    op.drop_column('bots', 'monthly_fee')
    op.drop_column('bots', 'strategy_type')
