"""add souls billing system

Revision ID: 002_souls_billing
Revises: 6fa94116b581
Create Date: 2026-04-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = '002_souls_billing'
down_revision: Union[str, None] = '6fa94116b581'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Remove old unused column ───────────────────────────────────────
    op.drop_column('users', 'subscription_tier')

    # ── 2. Add plan + souls_balance to users ──────────────────────────────
    op.add_column('users',
        sa.Column('plan', sa.String(20), nullable=False, server_default='tester')
    )
    op.add_column('users',
        sa.Column('souls_balance', sa.Integer(), nullable=False, server_default='600')
    )

    # ── 3. Create souls_transactions table ───────────────────────────────
    op.create_table(
        'souls_transactions',
        sa.Column('id',            UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',       UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('amount',        sa.Integer(),        nullable=False),
        sa.Column('reason',        sa.String(50),       nullable=False),
        sa.Column('balance_after', sa.Integer(),        nullable=False),
        sa.Column('meta',          JSONB,               nullable=True),
        sa.Column('created_at',    sa.DateTime(),       server_default=sa.func.now()),
    )
    op.create_index('ix_souls_transactions_user_id',    'souls_transactions', ['user_id'])
    op.create_index('ix_souls_transactions_created_at', 'souls_transactions', ['created_at'])

    # ── 4. Backfill transaction ledger for existing users ─────────────────
    # Every existing user gets a signup_tester entry so the ledger is complete.
    op.execute("""
        INSERT INTO souls_transactions (id, user_id, amount, reason, balance_after, created_at)
        SELECT
            gen_random_uuid(),
            id,
            600,
            'signup_tester',
            600,
            NOW()
        FROM users
    """)


def downgrade() -> None:
    op.drop_index('ix_souls_transactions_created_at', table_name='souls_transactions')
    op.drop_index('ix_souls_transactions_user_id',    table_name='souls_transactions')
    op.drop_table('souls_transactions')
    op.drop_column('users', 'souls_balance')
    op.drop_column('users', 'plan')
    op.add_column('users',
        sa.Column('subscription_tier', sa.String(50), server_default='free', nullable=True)
    )