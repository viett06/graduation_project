from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from decimal import Decimal


class InterestRateBase(BaseModel):
    min_amount: Optional[int] = None
    max_amount: Optional[int] = None
    term_month: int
    rate: Decimal
    effective_date: datetime
    is_current: bool = False
    note: Optional[str] = None
    bank_id: int

class InterestRateCreate(InterestRateBase):
    create_by: int

class BankOut(BaseModel):
    id: int
    name: str
    code: str

    model_config = ConfigDict(from_attributes=True)

class InterestRateUpdate(BaseModel):
    min_amount: Optional[int] = None
    max_amount: Optional[int] = None
    term_month: Optional[int] = None
    rate: Optional[Decimal] = None
    effective_date: Optional[datetime] = None
    is_current: Optional[bool] = None
    note: Optional[str] = None
    bank_id: Optional[int] = None

class InterestRateInDBBase(InterestRateBase):
    id: int
    create_by: int
    created_at: datetime
    updated_at: datetime
    bank: BankOut

    model_config = ConfigDict(from_attributes=True)

class InterestRateResponse(InterestRateInDBBase):
    pass





