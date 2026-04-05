from socket import fromfd

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

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

class BankInDBBase(BankBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class BankResponse(BankInDBBase):
    pass

class BankRateResponse(BaseModel):
    bank: str | None
    logo_url: str | None
    type: str | None
    rate: float | None
    updated_at: datetime | None
    rate_source: str | None



