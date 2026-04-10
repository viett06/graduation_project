from typing import List

from fastapi.encoders import jsonable_encoder

from app.enums.auditActionType import AuditActionType
from app.enums.auditLogEntryType import AuditLogEntryType
from app.models.interestRate import InterestRate
from sqlalchemy.orm import Session
from app.repository.interestRateRepository import InterestRateRepository
from app.schemas.interestRateSchema import InterestRateCreate, InterestRateUpdate
from sqlalchemy.exc import SQLAlchemyError

from app.service.auditLogService import AuditLogService


class InterestRateService:
    def __init__(self, session: Session):
        self.__interestRateRepository = InterestRateRepository(session=session)
        self.__auditLogService = AuditLogService(session=session)

    def create_interest_rate(self, data_rate: InterestRateCreate) -> InterestRate:

        exists_rate_of_month = self.__interestRateRepository.check_data_month_of_bank_exists(data_rate.bank_id, data_rate.term_month)

        if exists_rate_of_month:
            raise ValueError(f"Interest rate for month {data_rate.term_month} already exists for this bank.")

        interest_rate_dump = InterestRate(**data_rate.model_dump())

        interest_rate = self.__interestRateRepository.create_interest_rate(interest_rate_dump)

        return interest_rate

    def create_all_interest_rates_of_bank(self, data_rates: List[InterestRateCreate]) -> List[InterestRate] | None:

        valid_data_list = []
        for item in data_rates:
            if item is not None:
                valid_data_list.append(item)

        if len(valid_data_list) == 0:
            raise ValueError("Request body cannot be empty.")

        for data_rate in valid_data_list:
            current_bank_id = data_rate.bank_id
            current_month = data_rate.term_month

            is_existed = self.__interestRateRepository.check_data_month_of_bank_exists(
                bank_id=current_bank_id,
                month=current_month
            )

            if is_existed:

                raise ValueError(f"Interest rate for month {data_rate.term_month} already exists. Operation aborted.")

        created_records = []

        try:
            for data_rate in valid_data_list:

                new_interest_rate_model = InterestRate(**data_rate.model_dump())

                saved_record = self.__interestRateRepository.create_interest_rate_no_commit(new_interest_rate_model)

                created_records.append(saved_record)

            self.__interestRateRepository.commit()
            self.__interestRateRepository.refresh_all(created_records)
            return created_records

        except Exception as e:
            self.__interestRateRepository.rollback(e)

    def delete_interest_rate_and_save_audit_log(self, admin_id: int, interest_rate: int):

        interest_rate_db = self.__interestRateRepository.find_interest_rate_by_id(interest_rate)

        if interest_rate_db is None:
            raise ValueError("Bank existed")

        action_type = AuditActionType.DELETE

        entry_type = AuditLogEntryType.INTEREST_RATE

        entity_id = interest_rate_db.id

        old_value_json = jsonable_encoder(interest_rate_db)

        self.__auditLogService.create_audit_log(
            admin_id=admin_id,
            action_type=action_type,
            entry_type=entry_type,
            entity_id=entity_id,
            old_value=old_value_json,
            new_value=None,
        )

        self.__interestRateRepository.delete_rate(interest_rate_db)
        self.__interestRateRepository.commit()
        return {"message": "Delete successful", "id": interest_rate_db.id}


    def update_interest_rate(self, rate_id: int, admin_id: int, data_bank_update: InterestRateUpdate):

        interest_rate_db = self.__interestRateRepository.find_interest_rate_by_id(rate_id)

        if interest_rate_db is None:
            raise ValueError("interest rate does not exist")

        old_value_json = jsonable_encoder(interest_rate_db)

        entry_type = AuditLogEntryType.INTEREST_RATE

        entity_id = interest_rate_db.id

        update_data = data_bank_update.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(interest_rate_db, key, value)

        new_value_json = jsonable_encoder(interest_rate_db)

        action_type = AuditActionType.UPDATE

        self.__auditLogService.create_audit_log(
            admin_id=admin_id,
            action_type=action_type,
            entry_type=entry_type,
            entity_id=entity_id,
            old_value=old_value_json,
            new_value=new_value_json,
        )

        self.__interestRateRepository.update_rate(interest_rate_db)

        self.__interestRateRepository.commit()
        self.__interestRateRepository.refresh(interest_rate_db)

        return interest_rate_db








