"""baseline schema

Revision ID: 301a44efdd4f
Revises:
Create Date: 2026-07-10 16:23:19.052182

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '301a44efdd4f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password', sa.String(255), nullable=False),
        sa.Column('monthly_income', sa.Float, nullable=False),
        sa.Column('monthly_savings_target', sa.Float, nullable=False),
        sa.Column('active_emis', sa.Float, server_default='0.0'),
        sa.Column('recurring_bills', sa.Float, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'verdict_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('product_name', sa.String(300), nullable=False),
        sa.Column('product_url', sa.String(500), nullable=True),
        sa.Column('product_category', sa.String(100), nullable=True),
        sa.Column('verdict', sa.String(10), nullable=False),
        sa.Column('confidence_percentage', sa.Float, nullable=True),
        sa.Column('composite_score', sa.Float, nullable=True),
        sa.Column('user_agreed', sa.Boolean, nullable=True),
        sa.Column('purchased_anyway', sa.Boolean, nullable=True),
        sa.Column('is_on_watchlist', sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column('last_checked_price', sa.Float, nullable=True),
        sa.Column('target_price', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'purchase_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('product_name', sa.String(300), nullable=False),
        sa.Column('product_category', sa.String(100), nullable=False),
        sa.Column('product_url', sa.String(500), nullable=True),
        sa.Column('purchase_price', sa.Float, nullable=False),
        sa.Column('usage_duration_days', sa.Integer, nullable=True),
        sa.Column('is_returned', sa.Boolean, server_default=sa.false()),
        sa.Column('is_resold', sa.Boolean, server_default=sa.false()),
        sa.Column('regret_score', sa.Integer, nullable=True),
        sa.Column('verdict_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('verdict_history.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'agent_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('verdict_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('verdict_history.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('agent_name', sa.String(50), nullable=False),
        sa.Column('score_contributed', sa.Float, nullable=True),
        sa.Column('reasoning', sa.String, nullable=True),
        sa.Column('raw_data', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('agent_results')
    op.drop_table('purchase_history')
    op.drop_table('verdict_history')
    op.drop_table('users')
