"""add ranking_risk column to banks

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'banks',
        sa.Column('ranking_risk', sa.Integer(), nullable=False, server_default='5'),
    )
    op.alter_column('banks', 'ranking_risk', server_default=None)


def downgrade() -> None:
    op.drop_column('banks', 'ranking_risk')