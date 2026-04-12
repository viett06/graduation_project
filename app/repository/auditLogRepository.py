from sqlalchemy import text
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

    def get_audit_log(self, bank_id: int, term_month: int):
        query = text("""
                     SELECT al.old_value
                     FROM audit_logs AS al
                     WHERE al.action_type = 'DELETE'
                       AND al.entry_type = 'INTEREST_RATE'
                       AND (al.old_value ->> 'term_month')::int = :term_month
              AND (al.old_value ->> 'bank_id')::int = :bank_id
                       ORDER BY al.created_at DESC
                     """)

        # Trả về kết quả thực thi
        return self.__session.execute(query, {
            "term_month": term_month,
            "bank_id": bank_id
        }).fetchall()