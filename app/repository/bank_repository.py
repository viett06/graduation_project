from datetime import date
from typing import Optional, List
from sqlalchemy import select, desc, exists, text
from sqlalchemy.orm import Session, joinedload
from app.models.bank import Bank


class BankRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_bank_by_name(self, name:str)-> Optional[Bank]:
        bank = select(Bank).where(Bank.name == name)
        return self.session.execute(bank).scalar_one_or_none()


    def create_new_bank(self, Bank_obj: Bank)-> Bank:
        try:
            self.session.add(Bank_obj)
            self.session.commit()
            self.session.refresh(Bank_obj)
            return Bank_obj
        except Exception as e:
            self.session.rollback()
            raise e

    def get_bank_by_id(self, bank_id: int)-> Optional[Bank]:
        bank = select(Bank).where((Bank.id == bank_id) & (Bank.status == True))
        return self.session.execute(bank).scalars().one_or_none()

    def check_code_exists(self, bank_code: str) -> bool:

        stmt = select(exists().where(Bank.code == bank_code))

        return self.session.execute(stmt).scalar()

    def get_all_banks(self, skip: int =0, limit: int =10):
        banks = (select(Bank).order_by(Bank.id.asc())
                                      .offset(skip)
                                      .limit(limit)).where(Bank.status == True)

        return self.session.execute(banks).scalars().all()


    def delete_bank(self, bank_obj: Bank):
        try:
            bank_obj.status = False
            self.session.add(bank_obj)  # optional, nếu object đã attach thì không cần
            # self.session.commit()
            # self.session.refresh(bank_obj)
            return bank_obj
        except Exception as e:
            self.session.rollback()
            raise e

    def commit(self):
        self.session.commit()

    def refresh(self, bank_obj: Bank):
        self.session.refresh(bank_obj)

    def get_bank_rates(self, term_month: int, amount: float, skip: int = 0, size: int = 10):
        query = text("""
                     SELECT b.name,
                            b.logo_url,
                            b.type,
                            ir.rate,
                            ir.updated_at,
                            b.rate_source
                     FROM banks AS b
                              JOIN interest_rates AS ir
                                        ON b.id = ir.bank_id
                     WHERE 1=1
                        AND ir.term_month = :term_month
                       AND b.status = TRUE
                         AND (:type IS NULL OR b.type = :type) 
                       AND ir.min_amount <= :amount
                       AND (ir.max_amount > :amount OR ir.max_amount IS NULL)
                         ORDER BY ir.rate DESC
                         OFFSET :skip
                         LIMIT :size
                     """)

        result = self.session.execute(
            query,
            {
                "term_month": term_month,
                "amount": amount,
                "skip": skip,
                "size": size
            }
        )

        return result.fetchall()

    def get_bank_by_name_or_code_or_both(self, name: str, code: str) -> Optional[List[dict]]:
        query = text("""
                     SELECT *
                     FROM banks b
                     WHERE 
            (:code IS NULL AND :name IS NULL)
            OR (:code IS NOT NULL AND b.code = :code)
            OR (:name IS NOT NULL AND b.name = :name)
    """)
        result = self.session.execute(
            query,
            {
                "code": code,
                "name": name
            }
        )
        return result.mappings().all()

    def get_rates_of_bank(self, bank_id: int) -> Bank | None:
        # Sử dụng joinedload lồng object thay join trong sql
        return self.session.query(Bank).options(
            joinedload(Bank.interest_rates)
        ).filter(Bank.id == bank_id, Bank.status == True).first()

    def get_applied_rate(self, bank_id: int, term_month: int, amount: float, deposit_date: date):

        query = text("""
                     SELECT rate
                     FROM interest_rates
                     WHERE 1 = 1
                       AND  bank_id = :bank_id
                       AND term_month = :term_month
                       AND min_amount <= :amount
                       AND (max_amount > :amount OR max_amount IS NULL)
                       AND effective_date <= :deposit_date
                     ORDER BY effective_date DESC LIMIT 1
                     """)

        result = self.session.execute(query, {
            "bank_id": bank_id,
            "term_month": term_month,
            "amount": amount,
            "deposit_date": deposit_date
        }).fetchone()

        return result[0] if result else None

    def get_available_terms(self, bank_id: int) -> List[int]:

        query = select(text("DISTINCT term_month")).textual_select_collector_style()
        query = text("SELECT DISTINCT term_month FROM interest_rates WHERE bank_id = :bank_id ORDER BY term_month")
        result = self.session.execute(query, {"bank_id": bank_id}).fetchall()
        return [row[0] for row in result]

