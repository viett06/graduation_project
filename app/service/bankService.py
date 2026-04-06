from app.schemas.bankSchema import BankCreate, UpdateBank, BankRateResponse
from sqlalchemy.orm import Session
from app.models.bank import Bank
from typing import Optional, List
from app.repository.bank_repository import BankRepository
from app.service.auditLogService import AuditLogService
from app.enums.auditActionType import AuditActionType
from app.enums.auditLogEntryType import AuditLogEntryType
from fastapi.encoders import jsonable_encoder


class BankService:
    def __init__(self, session: Session):
        self.__bankRepository = BankRepository(session=session)
        self.__auditLogService = AuditLogService(session=session)

    def create_bank(self, data_bank: BankCreate):

        # existing_bank = self.__bankRepository.find_bank_by_name(data_bank.name)
        #
        # if existing_bank:
        #     raise ValueError("Bank already exists")

        # if self.__bankRepository.check_code_exists(data_bank.code):
        #     raise ValueError("Bank code already exists")

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

    def delete_bank_and_save_audit_log(self, admin_id:int, bank_id: int):

        bank = self.__bankRepository.get_bank_by_id(bank_id)

        if bank is None:
            raise ValueError("Bank existed")

        action_type = AuditActionType.DELETE

        entry_type = AuditLogEntryType.BANK

        entity_id = bank.id

        old_value_json = jsonable_encoder(bank)

        self.__auditLogService.create_audit_log(
            admin_id=admin_id,
            action_type=action_type,
            entry_type=entry_type,
            entity_id=entity_id,
            old_value=old_value_json,
            new_value= None,
        )



        self.__bankRepository.delete_bank(bank)
        self.__bankRepository.commit()
        return {"message": "Delete successful", "id": bank_id}

    def update_bank(self, bank_id: int, admin_id: int, data_bank_update: UpdateBank):
        bank = self.__bankRepository.get_bank_by_id(bank_id)

        if bank is None:
            raise ValueError("Bank not found")

        old_value_json = jsonable_encoder(bank)

        entry_type = AuditLogEntryType.BANK

        entity_id = bank.id

        update_data = data_bank_update.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(bank, key, value)

        new_value_json = jsonable_encoder(bank)

        action_type = AuditActionType.UPDATE

        self.__auditLogService.create_audit_log(
            admin_id=admin_id,
            action_type=action_type,
            entry_type=entry_type,
            entity_id=entity_id,
            old_value=old_value_json,
            new_value = new_value_json,
        )

        self.__bankRepository.update_bank(bank)

        self.__bankRepository.commit()
        self.__bankRepository.refresh(bank)

        return bank

    def get_banks_by_month_and_amount(self, term_month: int, amount: float = 0, page: int = 1, size: int = 10) -> List[BankRateResponse]:
        if page < 1:
            page = 1
        skip = (page - 1) * size

        rows = self.__bankRepository.get_bank_rates(term_month, amount, skip, size)

        print("ROWS:", rows)

        if rows is None:
            return []


        # new_list = [expression for item in iterable if condition] | list comprehension
        try:
            return [
                BankRateResponse(
                    bank = row.name,
                    logo_url=row.logo_url,
                    type=row.type,
                    rate=float(row.rate) if row.rate else None,
                    updated_at=row.updated_at,
                    rate_source=row.rate_source
                )
                for row in rows
            ]
        except Exception as e:
            print("ERROR:", e)
            raise













