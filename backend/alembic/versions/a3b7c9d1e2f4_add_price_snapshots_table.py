"""add price_snapshots table

Revision ID: a3b7c9d1e2f4
Revises: 9da9adc518dc
Create Date: 2026-08-01 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'a3b7c9d1e2f4'
down_revision: Union[str, None] = '9da9adc518dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'price_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('product_identifier', sa.String(300), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('platform', sa.String(100), nullable=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_price_snapshots_product_identifier', 'price_snapshots', ['product_identifier'])
    op.create_index('ix_price_snapshots_product_checked', 'price_snapshots', ['product_identifier', 'checked_at'])


def downgrade() -> None:
    op.drop_index('ix_price_snapshots_product_checked', table_name='price_snapshots')
    op.drop_index('ix_price_snapshots_product_identifier', table_name='price_snapshots')
    op.drop_table('price_snapshots')
