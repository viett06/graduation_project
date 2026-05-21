from datetime import date
from distutils.util import execute
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from app.models.interestRate import InterestRate
from app.models.bank import Bank
from sqlalchemy import bindparam, text
from sqlalchemy.sql import exists, select
from app.schemas.interestRateSchema import InterestRateBase, InterestRateCreate


class InterestRateRepository:
    def __init__(self, session: Session):
        self.__session: Session = session

    def create_interest_rate(self, data_interest_rate: InterestRate) -> InterestRate:
        try:
            self.__session.add(data_interest_rate)
            self.__session.commit()
            self.__session.refresh(data_interest_rate)
            return data_interest_rate
        except Exception as e:
            self.__session.rollback()
            raise e

    def create_interest_rate_no_commit(self, data_interest_rate: InterestRate):
        self.__session.add(data_interest_rate)
        self.__session.flush()
        return data_interest_rate

    def check_data_month_of_bank_exists(self, bank_id: int, month: int) -> bool:
        stmt = select(
            exists().where(
                InterestRate.bank_id == bank_id,
                InterestRate.term_month == month
            )
        )
        return bool(self.__session.execute(stmt).scalar())

    def get_bank_with_rate(self, bank_id: int):
        stmt = select(InterestRate).join(Bank).where(Bank.id == bank_id)
        return self.__session.execute(stmt).scalar()

    def commit(self):
        self.__session.commit()

    def refresh_all(self, items: List[InterestRate]) -> None:
        """Refresh multiple objects from the database."""
        for item in items:
            self.__session.refresh(item)

    def rollback(self, error: Exception):
        self.__session.rollback()
        raise error

    def refresh(self, interest_rate: InterestRate):
        self.__session.refresh(interest_rate)

    def delete_rate(self, interest_rate: InterestRate):
        try:
            self.__session.delete(interest_rate)
            # self.session.commit()
            # self.session.refresh(bank_obj)
            return interest_rate
        except Exception as e:
            self.__session.rollback()
            raise e

    def update_rate(self, interest_rate: InterestRate)-> InterestRate:
        try:
            self.__session.add(interest_rate)
            # self.session.commit()
            # self.session.refresh(bank_obj)
            return interest_rate
        except Exception as e:
            self.__session.rollback()
            raise e

    def find_interest_rate_by_id(self, rate_id: int) -> Optional[InterestRate]:
        stmt = select(InterestRate).where(InterestRate.id == rate_id)
        return self.__session.execute(stmt).scalar_one_or_none()

    def get_best_rates(self, term_months: int, prefer_online: bool = True, as_of_date: date = None) -> Dict:
        """Trả về lãi suất tốt nhất cho kỳ hạn term_months (đơn vị %/năm)"""
        if as_of_date is None:
            as_of_date = date.today()

        query = self.db.query(InterestRate).filter(
            InterestRate.term_month == term_months,
            InterestRate.effective_date <= as_of_date,
            InterestRate.is_current == True
        )
        if prefer_online:
            query = query.filter(InterestRate.channel == "online")
        else:
            query = query.filter(InterestRate.channel == "counter")

        best = query.order_by(InterestRate.rate.desc()).first()
        if best:
            return {"rate": float(best.rate), "bank_id": best.bank_id, "channel": best.channel}

        # fallback: lấy bất kỳ kênh nào
        best = self.db.query(InterestRate).filter(
            InterestRate.term_month == term_months,
            InterestRate.effective_date <= as_of_date,
            InterestRate.is_current == True
        ).order_by(InterestRate.rate.desc()).first()
        if best:
            return {"rate": float(best.rate), "bank_id": best.bank_id, "channel": best.channel}

        return {"rate": 0.0, "bank_id": None, "channel": None}

    def get_available_terms_for_chatbot(
            self,
            codes: list[str] | None = None,
            channel: str | None = None
    ):
        query_text = """
            SELECT DISTINCT UPPER(b.code) AS code,
                            b.name AS bank_name,
                            ir.term_month,
                            UPPER(ir.channel) AS channel
            FROM interest_rates AS ir
            JOIN banks AS b ON b.id = ir.bank_id
            WHERE b.status = TRUE
              AND ir.rate IS NOT NULL
              AND (:channel IS NULL OR UPPER(ir.channel) = UPPER(:channel))
              AND (:has_codes = FALSE OR UPPER(b.code) IN :codes)
            ORDER BY UPPER(b.code), ir.term_month
        """

        normalized_codes = [code.strip().upper() for code in (codes or []) if code]
        query = text(query_text).bindparams(bindparam("codes", expanding=True))
        return self.__session.execute(
            query,
            {
                "channel": channel,
                "has_codes": len(normalized_codes) > 0,
                "codes": normalized_codes or ["__NO_CODE__"],
            }
        ).mappings().all()

    def get_top_rates_for_chatbot(
            self,
            term_month: int | None = None,
            channel: str | None = None,
            amount: float | None = None,
            limit: int = 10
    ):
        query = text("""
            SELECT b.id AS bank_id,
                   b.name AS bank_name,
                   UPPER(b.code) AS code,
                   UPPER(b.type) AS type,
                   ir.rate,
                   ir.term_month,
                   UPPER(ir.channel) AS channel,
                   ir.min_amount,
                   ir.max_amount,
                   ir.effective_date,
                   ir.updated_at
            FROM interest_rates AS ir
            JOIN banks AS b ON b.id = ir.bank_id
            WHERE b.status = TRUE
              AND ir.rate IS NOT NULL
              AND (:term_month IS NULL OR ir.term_month = :term_month)
              AND (:channel IS NULL OR UPPER(ir.channel) = UPPER(:channel))
              AND (:amount IS NULL OR (
                    ir.min_amount <= :amount
                    AND (ir.max_amount > :amount OR ir.max_amount IS NULL)
              ))
            ORDER BY ir.rate DESC, b.name ASC
            LIMIT :limit
        """)
        return self.__session.execute(
            query,
            {
                "term_month": term_month,
                "channel": channel,
                "amount": amount,
                "limit": limit,
            }
        ).mappings().all()


