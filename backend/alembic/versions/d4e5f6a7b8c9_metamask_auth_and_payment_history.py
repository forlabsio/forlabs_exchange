"""metamask auth and payment history

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-26 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users table: replace email/password with wallet_address ---
    op.drop_index('ix_users_email', table_name='users')
    op.drop_column('users', 'email')
    op.drop_column('users', 'password_hash')
    op.add_column('users', sa.Column('wallet_address', sa.String(), nullable=False))
    op.create_index(op.f('ix_users_wallet_address'), 'users', ['wallet_address'], unique=True)

    # --- bot_subscriptions: add payment fields ---
    op.add_column('bot_subscriptions', sa.Column('tx_hash', sa.String(), nullable=True))
    op.add_column('bot_subscriptions', sa.Column('payment_amount', sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column('bot_subscriptions', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))

    # --- payment_history: new table ---
    op.create_table(
        'payment_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('bot_id', sa.Integer(), sa.ForeignKey('bots.id'), nullable=False),
        sa.Column('tx_hash', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('network', sa.String(length=20), server_default='polygon'),
        sa.Column('verified_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(op.f('ix_payment_history_tx_hash'), 'payment_history', ['tx_hash'], unique=True)


def downgrade() -> None:
    # --- payment_history: drop table ---
    op.drop_index(op.f('ix_payment_history_tx_hash'), table_name='payment_history')
    op.drop_table('payment_history')

    # --- bot_subscriptions: remove payment fields ---
    op.drop_column('bot_subscriptions', 'expires_at')
    op.drop_column('bot_subscriptions', 'payment_amount')
    op.drop_column('bot_subscriptions', 'tx_hash')

    # --- users table: restore email/password, remove wallet_address ---
    op.drop_index(op.f('ix_users_wallet_address'), table_name='users')
    op.drop_column('users', 'wallet_address')
    op.add_column('users', sa.Column('email', sa.String(), nullable=False))
    op.add_column('users', sa.Column('password_hash', sa.String(), nullable=False))
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
