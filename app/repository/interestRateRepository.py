from distutils.util import execute
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.interestRate import InterestRate
from app.models.bank import Bank
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

