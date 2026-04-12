from sqlalchemy import text
from sqlalchemy.dialects.mssql import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.models.auditLog import AuditLog
from app.repository.auditLogRepository import AuditLogRepository
from app.schemas.auditLogSchema import AuditLogRate


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

    def get_audit_log(self, bank_id: int, term_month: int) -> list[AuditLogRate]:
        # mỗi row chứa tuple/dict old_value
        data_rates = self.__auditLogRepository.get_audit_log(bank_id, term_month)

        response = []
        for row in data_rates:
            try:
                # row[0] thường là kết quả của cột đầu tiên trong SELECT (al.old_value)
                # Nếu old_value đã là dict (JSONB), ta truyền trực tiếp vào model_validate
                raw_dict = row[0]

                if raw_dict:
                    obj = AuditLogRate.model_validate(raw_dict)
                    response.append(obj)

            except Exception as e:

                print({e})
                continue

        return response
