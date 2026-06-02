from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status  # Thêm status ở đây
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.auditLogSchema import AuditLogRateHistory
from app.service.auditLogService import AuditLogService


router = APIRouter()


@router.get("/", response_model=AuditLogRateHistory)
async def get_bank_interest_audit_log(
        bank_id: int,
        term_month: int,
        channel: str,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        session: Session = Depends(deps.get_db),
):
    try:

        audit_log_service = AuditLogService(session)

        logs = audit_log_service.get_audit_log(
            bank_id=bank_id,
            term_month=term_month,
            channel=channel,
            created_from=created_from,
            created_to=created_to,
        )


        return logs

    except Exception as e:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Đã xảy ra lỗi khi lấy lịch sử: {str(e)}"
        )
