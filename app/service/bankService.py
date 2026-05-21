from datetime import datetime

from app.schemas.bankSchema import BankCreate, UpdateBank, BankRateResponse, InterestRateResponse, \
    InterestCalculateRequest, InterestCalculateResponse, AllBanksOfChatBot, CompareCalculateRequest, CompareCalculateResponse
from sqlalchemy.orm import Session
from app.models.bank import Bank
from typing import Any, Optional, List
from app.repository.bank_repository import BankRepository
from app.service.auditLogService import AuditLogService
from app.enums.auditActionType import AuditActionType
from app.enums.auditLogEntryType import AuditLogEntryType
from fastapi.encoders import jsonable_encoder
from datetime import date, timedelta
import calendar


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

    async def get_all_banks_and_rates_for_chat_bot(self, name: str | None, type: str | None, code: str | None):

        banks = await self.__bankRepository.get_all_banks_and_rates_for_chat_bot(name, type, code)

        list_of_banks = []

        for bank in banks:
            bank_data = AllBanksOfChatBot(
                code=bank.code,
                type=bank.type,
                rate=bank.rate,
                term_month=bank.term_month
            )
            list_of_banks.append(bank_data.model_dump())

        return list_of_banks

    def delete_bank_and_save_audit_log(self, admin_id:int, bank_id: int):

        bank = self.__bankRepository.get_bank_by_id(bank_id)

        if bank is None:
            raise ValueError("Bank not found")

        rates = self.__bankRepository.get_rates_for_delete_bank(bank_id)
        for rate in rates:
            self.__auditLogService.create_audit_log(
                admin_id=admin_id,
                action_type=AuditActionType.DELETE,
                entry_type=AuditLogEntryType.INTEREST_RATE,
                entity_id=rate['id'],
                old_value=jsonable_encoder(rate),
                new_value=None
            )

        action_type_bank = AuditActionType.DELETE

        entry_type_bank = AuditLogEntryType.BANK

        entity_id_bank = bank.id

        old_value_json_bank = jsonable_encoder(bank)

        self.__auditLogService.create_audit_log(
            admin_id=admin_id,
            action_type=action_type_bank,
            entry_type=entry_type_bank,
            entity_id=entity_id_bank,
            old_value=old_value_json_bank,
            new_value= None,
        )

        self.__bankRepository.delete_rates_of_bank(bank.id)

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

    def get_banks_by_month_and_amount(self, term_month: int, amount: float = 0, type: str = None,  page: int = 1, size: int = 10) -> List[BankRateResponse]:
        if page < 1:
            page = 1
        skip = (page - 1) * size

        rows = self.__bankRepository.get_bank_rates(term_month, amount,type, skip, size)

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
                    channel=row.channel,
                    rate=float(row.rate) if row.rate else None,
                    updated_at=row.updated_at,
                    rate_source=row.rate_source
                )
                for row in rows
            ]
        except Exception as e:
            print("ERROR:", e)
            raise


    def get_bank_by_name_or_code_or_both(self, name: str, code: str) -> Optional[List[Bank]]:

        banks = self.__bankRepository.get_bank_by_name_or_code_or_both(name, code)

        return [Bank(**bank) for bank in banks]

    def get_rates_of_bank(self, bank_id: int) -> Bank | None:
            bank = self.__bankRepository.get_rates_of_bank(bank_id)
            return bank

    def calculate_maturity_date(self, deposit_date: date, term_month: int) -> date:

        month = deposit_date.month - 1 + term_month
        year = deposit_date.year + month // 12
        month = month % 12 + 1
        day = min(deposit_date.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    def calculate_interest(self, calc_data: InterestCalculateRequest) -> InterestCalculateResponse:

        bank = self.__bankRepository.get_bank_by_id(calc_data.bank_id)
        if not bank:
            raise ValueError("The bank does not exist or has been hidden.")

        rate = self.__bankRepository.get_applied_rate(
            calc_data.bank_id,
            calc_data.term_month,
            calc_data.amount,
            calc_data.deposit_date,
            calc_data.channel
        )

        if rate is None:
            raise ValueError(
                f"No suitable interest rate found for this term. {calc_data.term_month} month at this time.")

        maturity_date = self.calculate_maturity_date(calc_data.deposit_date, calc_data.term_month)
        total_days = (maturity_date - calc_data.deposit_date).days

        #Actual/365: Tiền lãi = Gốc * %Lãi * (Số ngày / 365)
        # interest_amount = calc_data.amount * (rate / 100) * (total_days / 365)
        interest_amount = calc_data.amount * (float(rate) / 100) * (total_days / 365)

        return InterestCalculateResponse(
            bank_name=bank.name,
            interest_rate=rate,
            channel = calc_data.channel,
            term_month=calc_data.term_month,
            deposit_date=calc_data.deposit_date,
            maturity_date=maturity_date,
            total_days=total_days,
            interest_amount=round(interest_amount, 2),
            total_amount=round(calc_data.amount + interest_amount, 2)
        )

    # def get_bank_terms(self, bank_id: int) -> List[int]:
    #     return self.__bankRepository.get_available_terms(bank_id)

    def compare_calculate_interest(self, calc_data: CompareCalculateRequest) -> CompareCalculateResponse:
        bank = self.__bankRepository.get_bank_by_id(calc_data.bank_id)
        if not bank:
            raise ValueError("The bank does not exist or has been hidden.")
        rate = self.__bankRepository.get_applied_rate(
            calc_data.bank_id,
            calc_data.term_month,
            calc_data.amount,
            calc_data.deposit_date,
            calc_data.channel
        )

        maturity_date = self.calculate_maturity_date(calc_data.deposit_date, calc_data.term_month)
        total_days = (maturity_date - calc_data.deposit_date).days

        interest_amount = calc_data.amount * (float(rate) / 100) * (total_days / 365)

        total_amount = round(calc_data.amount + interest_amount, 2)

        return CompareCalculateResponse(
            bank_name=bank.name,
            interest_rate=rate,
            channel=calc_data.channel,
            term_month=calc_data.term_month,
            deposit_date=calc_data.deposit_date,
            maturity_date=maturity_date,
            total_days=total_days,
            interest_amount=round(interest_amount, 2),
            total_amount=total_amount,
            compare_result= total_amount - calc_data.previous_result,
        )

    @staticmethod
    def _chatbot_rate_row(row) -> dict[str, Any]:
        data = dict(row)
        if data.get("rate") is not None:
            data["rate"] = float(data["rate"])
        return data

    def resolve_banks_for_chatbot(
            self,
            codes: list[str] | None = None,
            names: list[str] | None = None,
            limit: int = 10
    ) -> list[dict[str, Any]]:
        rows = self.__bankRepository.find_banks_for_chatbot(codes=codes, names=names, limit=limit)
        return [dict(row) for row in rows]

    def get_rates_for_chatbot(
            self,
            codes: list[str] | None = None,
            names: list[str] | None = None,
            term_month: int | None = None,
            channel: str | None = None,
            amount: float | None = None,
            limit: int = 20
    ) -> list[dict[str, Any]]:
        rows = self.__bankRepository.get_interest_rates_for_chatbot(
            codes=codes,
            names=names,
            term_month=term_month,
            channel=channel,
            amount=amount,
            limit=limit,
        )
        return [self._chatbot_rate_row(row) for row in rows]

    def get_top_rates_for_chatbot(
            self,
            term_month: int | None = None,
            channel: str | None = None,
            amount: float | None = None,
            limit: int = 10
    ) -> list[dict[str, Any]]:
        rows = self.__bankRepository.get_top_interest_rates_for_chatbot(
            term_month=term_month,
            channel=channel,
            amount=amount,
            limit=limit,
        )
        return [self._chatbot_rate_row(row) for row in rows]

    def compare_interest_for_chatbot(
            self,
            codes: list[str] | None = None,
            names: list[str] | None = None,
            term_month: int | None = None,
            amount: float | None = None,
            channel: str = "ONLINE",
            deposit_date: date | None = None
    ) -> dict[str, Any]:
        banks = self.resolve_banks_for_chatbot(codes=codes, names=names, limit=2)

        if len(banks) < 2:
            return {
                "error": "Cần tìm được ít nhất 2 ngân hàng để so sánh.",
                "matched_banks": banks,
            }

        missing_fields = []
        if term_month is None:
            missing_fields.append("term_month")
        if amount is None:
            missing_fields.append("amount")

        rate_rows = self.get_rates_for_chatbot(
            codes=[bank["code"] for bank in banks],
            term_month=term_month,
            channel=channel,
            amount=amount,
            limit=10,
        )

        if missing_fields:
            return {
                "missing_fields": missing_fields,
                "matched_banks": banks,
                "rates": rate_rows,
                "message": "Cần bổ sung số tiền gửi và kỳ hạn để tính tiền lãi.",
            }

        deposit_date_value = deposit_date or date.today()
        results = []

        for bank in banks:
            try:
                calc_request = InterestCalculateRequest(
                    bank_id=bank["id"],
                    channel=channel,
                    term_month=term_month,
                    amount=amount,
                    deposit_date=deposit_date_value,
                )
                results.append(self.calculate_interest(calc_request).model_dump())
            except Exception as e:
                results.append({
                    "bank_name": bank["name"],
                    "code": bank["code"],
                    "error": str(e),
                })

        valid_results = [item for item in results if not item.get("error")]
        if len(valid_results) < 2:
            return {
                "matched_banks": banks,
                "rates": rate_rows,
                "calculations": results,
                "error": "Không đủ dữ liệu lãi suất phù hợp để tính tiền lãi cho cả hai ngân hàng.",
            }

        first_total = valid_results[0]["total_amount"]
        comparisons = []
        for item in valid_results[1:]:
            comparisons.append({
                "bank_name": item["bank_name"],
                "compare_result": item["total_amount"] - first_total,
            })

        best = max(valid_results, key=lambda item: item["total_amount"])
        worst = min(valid_results, key=lambda item: item["total_amount"])

        return {
            "matched_banks": banks,
            "rates": rate_rows,
            "calculations": valid_results,
            "comparisons": comparisons,
            "better_bank": best["bank_name"],
            "difference_total_amount": round(best["total_amount"] - worst["total_amount"], 2),
            "difference_interest_amount": round(best["interest_amount"] - worst["interest_amount"], 2),
            "amount": amount,
            "term_month": term_month,
            "channel": channel,
            "deposit_date": deposit_date_value,
        }












