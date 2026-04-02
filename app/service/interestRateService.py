from typing import List
from app.models.interestRate import InterestRate
from sqlalchemy.orm import Session
from app.repository.interestRateRepository import InterestRateRepository
from app.schemas.interestRateSchema import InterestRateCreate
from sqlalchemy.exc import SQLAlchemyError

class InterestRateService:
    def __init__(self, session: Session):
        self.__interestRateRepository = InterestRateRepository(session=session)

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








