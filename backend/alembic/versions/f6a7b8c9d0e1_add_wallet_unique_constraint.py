"""add wallet unique constraint

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-27 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_wallet_user_asset", "wallets", ["user_id", "asset"])


def downgrade() -> None:
    op.drop_constraint("uq_wallet_user_asset", "wallets", type_="unique")
