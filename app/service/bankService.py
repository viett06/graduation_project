from app.schemas.bankSchema import BankCreate
from sqlalchemy.orm import Session
from app.models.bank import Bank
from typing import Optional
from app.repository.bank_repository import BankRepository

class BankService:
    def __init__(self, session: Session):
        self.__bankRepository = BankRepository(session=session)

    def create_bank(self, data_bank: BankCreate):

        existing_bank = self.__bankRepository.find_bank_by_name(data_bank.name)

        if existing_bank:
            raise ValueError("Bank already exists")

        if self.__bankRepository.check_code_exists(data_bank.code):
            raise ValueError("Bank code already exists")

        bank = Bank(**data_bank.model_dump())

        return self.__bankRepository.create_new_bank(bank)

    def get_bank_by_id(self, bank_id: int)-> Optional[Bank]:

        return self.__bankRepository.get_bank_by_id(bank_id)

    def check_code_exists(self, bank_code:str):
        return self.__bankRepository.check_code_exists(bank_code)

    def get_all_banks(self, page: int = 1, size: int = 10) -> list[Bank]:

        if page < 1: page = 1
        skip = (page - 1) * size

        return self.__bankRepository.get_all_banks(skip=skip, limit=size)





