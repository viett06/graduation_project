from datetime import datetime

from sqlalchemy import text
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

    def get_audit_log(
            self,
            bank_id: int,
            term_month: int,
            channel: str,
            created_from: datetime | None = None,
            created_to: datetime | None = None,
    ):
        query = text("""
            WITH audit_rows AS (
                SELECT al.id AS audit_id,
                       NULL::int AS rate_id,
                       al.action_type,
                       al.created_at AS changed_at,
                       al.created_at::date AS changed_date,
                       (al.old_value ->> 'bank_id')::int AS bank_id,
                       b.code AS bank_code,
                       b.name AS bank_name,
                       (al.old_value ->> 'term_month')::int AS term_month,
                       UPPER(al.old_value ->> 'channel') AS channel,
                       (al.old_value ->> 'rate')::numeric AS rate,
                       (al.old_value ->> 'effective_date')::timestamp AS effective_date,
                       FALSE AS is_current,
                       'audit_log' AS source,
                       0 AS sort_order
                FROM audit_logs AS al
                LEFT JOIN banks AS b
                    ON b.id = (al.old_value ->> 'bank_id')::int
                WHERE al.entry_type = 'INTEREST_RATE'
                  AND al.action_type IN ('UPDATE', 'DELETE')
                  AND (al.old_value ->> 'term_month')::int = :term_month
                  AND (al.old_value ->> 'bank_id')::int = :bank_id
                  AND UPPER(al.old_value ->> 'channel') = UPPER(:channel)
                  AND (:created_from IS NULL OR al.created_at >= :created_from)
                  AND (:created_to IS NULL OR al.created_at <= :created_to)
            ),
            current_row AS (
                SELECT NULL::int AS audit_id,
                       ir.id AS rate_id,
                       'CURRENT' AS action_type,
                       COALESCE(ir.updated_at, ir.created_at, ir.effective_date) AS changed_at,
                       COALESCE(ir.updated_at, ir.created_at, ir.effective_date)::date AS changed_date,
                       ir.bank_id,
                       b.code AS bank_code,
                       b.name AS bank_name,
                       ir.term_month,
                       UPPER(ir.channel) AS channel,
                       ir.rate AS rate,
                       ir.effective_date,
                       TRUE AS is_current,
                       'current' AS source,
                       1 AS sort_order
                FROM interest_rates AS ir
                JOIN banks AS b ON b.id = ir.bank_id
                WHERE ir.bank_id = :bank_id
                  AND ir.term_month = :term_month
                  AND UPPER(ir.channel) = UPPER(:channel)
                  AND ir.is_current = TRUE
                ORDER BY ir.effective_date DESC, ir.updated_at DESC, ir.id DESC
                LIMIT 1
            )
            SELECT *
            FROM (
                SELECT * FROM audit_rows
                UNION ALL
                SELECT * FROM current_row
            ) AS history
            ORDER BY history.sort_order ASC, history.changed_at ASC, history.audit_id ASC NULLS LAST
                     """)

        # Trả về kết quả thực thi
        return self.__session.execute(query, {
            "term_month": term_month,
            "bank_id": bank_id,
            "channel": channel,
            "created_from": created_from,
            "created_to": created_to,
        }).mappings().all()
