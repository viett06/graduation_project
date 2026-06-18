"""drop ranking_risk group check constraint on banks

ranking_risk là mã nhóm do admin tự định nghĩa, không giới hạn giá trị cố định.
Các ngân hàng cùng nhóm có cùng giá trị ranking_risk.

Revision ID: a1b2c3d4e5f6
Revises: f5a6b7c8d9e0
Create Date: 2026-06-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE banks
        DROP CONSTRAINT IF EXISTS ck_banks_ranking_risk_group
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_banks_ranking_risk_group'
            ) THEN
                UPDATE banks
                SET ranking_risk = 2
                WHERE ranking_risk IS NULL OR ranking_risk NOT IN (1, 2, 3);

                ALTER TABLE banks
                ADD CONSTRAINT ck_banks_ranking_risk_group
                CHECK (ranking_risk IN (1, 2, 3));
            END IF;
        END $$;
    """)