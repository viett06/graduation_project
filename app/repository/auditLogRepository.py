from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.models.auditLog import AuditLog


class AuditLogRepository:
    def __init__(self, session: Session):
        self.__session = session

    def create_audit_log(self,
                         admin_id: int,
                         action_type: str,
                         entry_type: str,
                         entity_id: int,
                         old_value: dict,
                         new_value: dict | None):
        audit_log = AuditLog(admin_id=admin_id,
                             action_type=action_type,
                             entry_type=entry_type,
                             entity_id=entity_id,
                             old_value=old_value,
                             new_value=new_value)
        self.__session.add(audit_log)
        return audit_log
