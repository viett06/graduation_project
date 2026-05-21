from datetime import date
from typing import Optional, List
from sqlalchemy import select, desc, exists, text, bindparam
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
            self.session.add(bank_obj)  # optional,
            # self.session.commit()
            # self.session.refresh(bank_obj)
            return bank_obj
        except Exception as e:
            self.session.rollback()
            raise e

    def delete_rates_of_bank(self, bank_id: int):
        query = text("""
        DELETE FROM interest_rates
            WHERE bank_id = :bank_id
        """)
        try:
            self.session.execute(query, {"bank_id": bank_id})
            # self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"error: {e}")
            raise e

    def get_rates_for_delete_bank(self, bank_id: int):
        query = text("SELECT * FROM interest_rates WHERE bank_id = :bank_id")
        return self.session.execute(query, {"bank_id": bank_id}).mappings().all()

    def commit(self):
        self.session.commit()

    def refresh(self, bank_obj: Bank):
        self.session.refresh(bank_obj)

    def get_bank_rates(self, term_month: int, amount: float,type: str,  skip: int = 0, size: int = 10):
        query = text("""
                     SELECT b.name,
                            b.logo_url,
                            b.type,
                            ir.rate,
                            ir.channel,
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
                "size": size,
                "type": type
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

    def get_applied_rate(self, bank_id: int, term_month: int, amount: float, deposit_date: date, channel: str):

        query = text("""
                     SELECT rate
                     FROM interest_rates
                     WHERE 1 = 1
                       AND  bank_id = :bank_id
                       AND term_month = :term_month
                       AND channel = :channel
                       AND min_amount <= :amount
                       AND (max_amount > :amount OR max_amount IS NULL)
                       AND effective_date <= :deposit_date
                     ORDER BY effective_date DESC LIMIT 1
                     """)

        result = self.session.execute(query, {
            "bank_id": bank_id,
            "term_month": term_month,
            "amount": amount,
            "deposit_date": deposit_date,
            "channel": channel
        }).fetchone()

        return result[0] if result else None

    def get_available_terms(self, bank_id: int) -> List[int]:

        query = select(text("DISTINCT term_month")).textual_select_collector_style()
        query = text("SELECT DISTINCT term_month FROM interest_rates WHERE bank_id = :bank_id ORDER BY term_month")
        result = self.session.execute(query, {"bank_id": bank_id}).fetchall()
        return [row[0] for row in result]

    async def get_all_banks_and_rates_for_chat_bot(self, name: str | None, type: str | None, code: str | None):

        search_name = f"%{name.strip()}%" if name else None
        search_type = f"%{type.strip().upper()}%" if type else None
        search_code = code.strip().upper() if code else None

        query = text("""
                                 SELECT b.name,
                   UPPER(b.code) as code,
                   UPPER(b.type) as type,
                   ir.rate,
                   ir.term_month
            FROM banks as b
            LEFT JOIN interest_rates AS ir ON b.id = ir.bank_id
            WHERE ir.rate IS NOT NULL
                  AND (
                        (:code IS NOT NULL AND UPPER(b.code) = :code)
                     OR (:code IS NULL AND (:name IS NULL OR b.name ILIKE :name))
                     )
                  AND (:type IS NULL OR UPPER(b.type) LIKE :type)
            ORDER BY ir.rate DESC
                     """)

        result = self.session.execute(query, {
            "name": search_name,
            "type": search_type,
            "code": search_code
        }).fetchall()

        return result

    def get_all_banks_and_rates_follow_duration_month(
            self,
            term_month: int,
            codes: list[str] | None,
            channel: str = "ONLINE"
    ):
        query_text = """
                     SELECT b.id, \
                            b.code, \
                            b.name, \
                            ir.term_month, \
                            ir.rate
                     FROM banks AS b
                              LEFT JOIN interest_rates AS ir
                                        ON b.id = ir.bank_id
                     WHERE b.status = TRUE
                       AND ir.rate IS NOT NULL
                       AND ir.term_month <= :term_month
                       AND UPPER(ir.channel) = UPPER(:channel) {code_filter}
                     ORDER BY ir.rate DESC \
                     """

        params = {
            "term_month": term_month,
            "channel": channel
        }

        if codes:
            query = text(
                query_text.format(code_filter="AND b.code IN :codes")
            ).bindparams(bindparam("codes", expanding=True))

            params["codes"] = list(codes)
        else:
            query = text(query_text.format(code_filter=""))

        result = self.session.execute(query, params).fetchall()
        return result

    def find_banks_for_chatbot(
            self,
            codes: list[str] | None = None,
            names: list[str] | None = None,
            limit: int = 10
    ):
        query_text = """
            SELECT id, name, UPPER(code) AS code, UPPER(type) AS type
            FROM banks
            WHERE status = TRUE
              AND (
                    (:has_codes = FALSE AND :has_names = FALSE)
                 OR (:has_codes = TRUE AND UPPER(code) IN :codes)
                 OR (:has_names = TRUE AND name ILIKE ANY(:names))
              )
            ORDER BY name ASC
            LIMIT :limit
        """

        normalized_codes = [code.strip().upper() for code in (codes or []) if code]
        normalized_names = [f"%{name.strip()}%" for name in (names or []) if name]

        query = text(query_text).bindparams(bindparam("codes", expanding=True))
        return self.session.execute(
            query,
            {
                "has_codes": len(normalized_codes) > 0,
                "has_names": len(normalized_names) > 0,
                "codes": normalized_codes or ["__NO_CODE__"],
                "names": normalized_names or ["__NO_NAME__"],
                "limit": limit,
            }
        ).mappings().all()

    def get_interest_rates_for_chatbot(
            self,
            codes: list[str] | None = None,
            names: list[str] | None = None,
            term_month: int | None = None,
            channel: str | None = None,
            amount: float | None = None,
            limit: int = 20
    ):
        query_text = """
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
                   ir.updated_at,
                   b.rate_source
            FROM banks AS b
            JOIN interest_rates AS ir ON b.id = ir.bank_id
            WHERE b.status = TRUE
              AND ir.rate IS NOT NULL
              AND (:term_month IS NULL OR ir.term_month = :term_month)
              AND (:channel IS NULL OR UPPER(ir.channel) = UPPER(:channel))
              AND (:amount IS NULL OR (
                    ir.min_amount <= :amount
                    AND (ir.max_amount > :amount OR ir.max_amount IS NULL)
              ))
              AND (
                    (:has_codes = FALSE AND :has_names = FALSE)
                 OR (:has_codes = TRUE AND UPPER(b.code) IN :codes)
                 OR (:has_names = TRUE AND b.name ILIKE ANY(:names))
              )
            ORDER BY ir.rate DESC, b.name ASC, ir.term_month ASC
            LIMIT :limit
        """

        normalized_codes = [code.strip().upper() for code in (codes or []) if code]
        normalized_names = [f"%{name.strip()}%" for name in (names or []) if name]

        query = text(query_text).bindparams(bindparam("codes", expanding=True))
        return self.session.execute(
            query,
            {
                "term_month": term_month,
                "channel": channel,
                "amount": amount,
                "has_codes": len(normalized_codes) > 0,
                "has_names": len(normalized_names) > 0,
                "codes": normalized_codes or ["__NO_CODE__"],
                "names": normalized_names or ["__NO_NAME__"],
                "limit": limit,
            }
        ).mappings().all()

    def get_top_interest_rates_for_chatbot(
            self,
            term_month: int | None = None,
            channel: str | None = None,
            amount: float | None = None,
            limit: int = 10
    ):
        return self.get_interest_rates_for_chatbot(
            codes=None,
            names=None,
            term_month=term_month,
            channel=channel,
            amount=amount,
            limit=limit,
        )
