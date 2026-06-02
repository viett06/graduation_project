from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict


class AuditLogBase(BaseModel):
    id: str
    admin_id: str
    action_type: str
    entry_type: str
    entity_id: int
    old_value: Optional[Union[dict, list]] = None
    new_value: Optional[Union[dict, list]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AuditLogRate(BaseModel):
    audit_id: int
    action_type: str
    entry_type: str
    created_at: datetime
    changed_date: date
    bank_id: int
    bank_code: Optional[str] = None
    bank_name: Optional[str] = None
    min_amount: Optional[int] = None
    max_amount: Optional[int] = None
    term_month: int
    channel: str
    rate: Decimal
    deleted_rate: Decimal
    effective_date: datetime
    is_current: bool = False
    note: Optional[str] = None
    current_rate: Optional[Decimal] = None
    current_rate_id: Optional[int] = None
    current_effective_date: Optional[datetime] = None
    old_value: Optional[Union[dict, list]] = None

class AuditLogRateHistoryPoint(BaseModel):
    rate: Decimal
    changed_at: Optional[datetime] = None
    changed_date: Optional[date] = None
    source: str
    action_type: Optional[str] = None
    audit_id: Optional[int] = None
    rate_id: Optional[int] = None
    effective_date: Optional[datetime] = None
    is_current: bool = False

class AuditLogRateHistory(BaseModel):
    bank_id: int
    bank_code: Optional[str] = None
    bank_name: Optional[str] = None
    term_month: int
    channel: str
    rates: List[Decimal]
    change_times: List[Optional[datetime]]
    points: List[AuditLogRateHistoryPoint]
