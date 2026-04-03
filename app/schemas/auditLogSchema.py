from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy.dialects.postgresql import JSONB


class AuditLogBase(BaseModel):
    id: str
    admin_id: str
    action_type: str
    entry_type: str
    entity_id: int
    old_value: JSONB
    new_value: JSONB
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

