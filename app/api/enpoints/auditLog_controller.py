from fastapi import APIRouter, Depends, HTTPException, status  # Thêm status ở đây
from sqlalchemy.orm import Session
from typing import List

from app.api import deps
from app.schemas.auditLogSchema import AuditLogRate
from app.service.auditLogService import AuditLogService


router = APIRouter()


@router.get("/", response_model=List[AuditLogRate])
async def get_bank_interest_audit_log(
        bank_id: int,
        term_month: int,
        session: Session = Depends(deps.get_db),
):
    try:

        audit_log_service = AuditLogService(session)

        logs = audit_log_service.get_audit_log(bank_id, term_month)


        return logs

    except Exception as e:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Đã xảy ra lỗi khi lấy lịch sử: {str(e)}"
        )