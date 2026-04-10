from socket import fromfd

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime


class BankBase(BaseModel):
    name: str
    code: str
    type: str
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    rate_source: Optional[str] = None
    status: bool = True

class BankCreate(BankBase):
    pass

class UpdateBank(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    type: Optional[str] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    rate_source: Optional[str] = None
    status: Optional[bool] = True

class InterestRateResponse(BaseModel):
    id: int
    rate: float | None
    created_at: datetime
    updated_at: datetime
    term_month: int | None
    min_amount: int | None
    max_amount: int | None

    model_config = ConfigDict(from_attributes=True)



class BankInDBBase(BankBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class BankResponse(BankInDBBase):
    interest_rates: list[InterestRateResponse] = []

    model_config = ConfigDict(from_attributes=True)

class BankRateResponse(BaseModel):
    bank: str | None
    logo_url: str | None
    type: str | None
    rate: float | None
    updated_at: datetime | None
    rate_source: str | None

class InterestCalculateRequest(BaseModel):
    bank_id: int
    term_month: int
    amount: float = Field(gt=0, description="The deposit amount must be greater than 0.")
    deposit_date: date = Field(default_factory=date.today)

class InterestCalculateResponse(BaseModel):
    bank_name: str
    interest_rate: float
    term_month: int
    deposit_date: date
    maturity_date: date
    total_days: int
    interest_amount: float
    total_amount: float



