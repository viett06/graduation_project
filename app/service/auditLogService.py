from datetime import datetime

from sqlalchemy.orm import Session

from app.models.auditLog import AuditLog
from app.repository.auditLogRepository import AuditLogRepository
from app.schemas.auditLogSchema import AuditLogRateHistory, AuditLogRateHistoryPoint


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

    def get_audit_log(
            self,
            bank_id: int,
            term_month: int,
            channel: str,
            created_from: datetime | None = None,
            created_to: datetime | None = None,
    ) -> AuditLogRateHistory:
        normalized_channel = channel.upper()
        data_rates = self.__auditLogRepository.get_audit_log(
            bank_id=bank_id,
            term_month=term_month,
            channel=normalized_channel,
            created_from=created_from,
            created_to=created_to,
        )

        points: list[AuditLogRateHistoryPoint] = []
        bank_code = None
        bank_name = None

        for row in data_rates:
            try:
                data = dict(row)
                bank_code = bank_code or data.get("bank_code")
                bank_name = bank_name or data.get("bank_name")
                points.append(AuditLogRateHistoryPoint.model_validate(data))
            except Exception as e:
                print({e})
                continue

        return AuditLogRateHistory(
            bank_id=bank_id,
            bank_code=bank_code,
            bank_name=bank_name,
            term_month=term_month,
            channel=normalized_channel,
            rates=[point.rate for point in points],
            change_times=[point.changed_at for point in points],
            points=points,
        )
