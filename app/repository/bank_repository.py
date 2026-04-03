from typing import Optional
from sqlalchemy import select, desc, exists
from sqlalchemy.orm import Session
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
        bank = select(Bank).where(Bank.id == bank_id)
        return self.session.execute(bank).scalars().one_or_none()

    def check_code_exists(self, bank_code: str) -> bool:

        stmt = select(exists().where(Bank.code == bank_code))

        return self.session.execute(stmt).scalar()

    def get_all_banks(self, skip: int =0, limit: int =10):
        banks = (select(Bank).order_by(Bank.id.asc())
                                      .offset(skip)
                                      .limit(limit))

        return self.session.execute(banks).scalars().all()

    def delete_bank(self, bank_obj: Bank):
        try:
            self.session.delete(bank_obj)
            # self.session.commit()
            # self.session.refresh(bank_obj)
            return bank_obj
        except Exception as e:
            self.session.rollback()
            raise e

    def update_bank(self, bank_obj: Bank)-> Bank:
        try:
            self.session.add(bank_obj)
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
