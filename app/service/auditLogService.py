from sqlalchemy.dialects.mssql import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.models.auditLog import AuditLog
from app.repository.auditLogRepository import AuditLogRepository


class AuditLogService:
    def __init__(self, session: Session):
        self.__auditLogRepository = AuditLogRepository(session)

    def create_audit_log(self,
                         admin_id: int,
                         action_type: str,
                         entry_type: str,
                         entity_id: int,
                         old_value: dict,
                         new_value: dict | None,
                         ) -> AuditLog:
        return self.__auditLogRepository.create_audit_log(admin_id,action_type, entry_type, entity_id, old_value, new_value)