from datetime import datetime
from decimal import Decimal
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict
from sqlalchemy.dialects.postgresql import JSONB


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
    min_amount: Optional[int] = None
    max_amount: Optional[int] = None
    term_month: int
    rate: Decimal
    effective_date: datetime
    is_current: bool = False
    note: Optional[str] = None
    bank_id: int

