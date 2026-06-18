"""enforce ranking_risk as risk group 1-3 on banks

ranking_risk là mã nhóm rủi ro:
  1 = Rủi ro thấp
  2 = Trung tính
  3 = Rủi ro cao

Các ngân hàng cùng nhóm có cùng giá trị ranking_risk.

Revision ID: f5a6b7c8d9e0
Revises: 3da9ab86086e
Create Date: 2026-06-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "3da9ab86086e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE banks
        SET ranking_risk = 2
        WHERE ranking_risk IS NULL OR ranking_risk NOT IN (1, 2, 3)
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_banks_ranking_risk_group'
            ) THEN
                ALTER TABLE banks
                ADD CONSTRAINT ck_banks_ranking_risk_group
                CHECK (ranking_risk IN (1, 2, 3));
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE banks
        DROP CONSTRAINT IF EXISTS ck_banks_ranking_risk_group
    """)