import logging

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict
from app.api.deps import get_db
from app.schemas.bankSchema import BankResponse
from sqlalchemy.orm import Session
from app.service.bankService import BankService, UpdateBank
from app.schemas.bankSchema import BankCreate
from app.core.security.rbac import PermissionEnum, RoleEnum
from app.core.security.guards import require_permissions, require_roles
from app.core.security.dependencies import get_current_active_user

router = APIRouter()
@router.post("",response_model=BankResponse)
async def create_bank(data_bank: BankCreate, session: Session = Depends(get_db)):
    bank_service = BankService(session)


    try:

        bank = bank_service.create_bank(data_bank)

        return bank
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{bank_id}",response_model=BankResponse)
async def get_detail_bank (bank_id: int, session: Session = Depends(get_db)):
    bank_service = BankService(session)
    try:
        bank = bank_service.get_bank_by_id(bank_id)
        return bank
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=List[BankResponse])
async def read_banks(
    page: int = 1,
    size: int = 10,
    session: Session = Depends(get_db)
):
    service = BankService(session)
    return service.get_all_banks(page=page, size=size)


@router.put("/{bank_id}",response_model=BankResponse)
async def update_bank(bank_id: int, data_update_bank: UpdateBank, session: Session = Depends(get_db), current_user: Dict = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.MANAGER)),):
    bank_service = BankService(session)
    admin_id = current_user.get("user_id")

    try:
        bank = bank_service.update_bank(bank_id, admin_id, data_update_bank)
        if not bank:
            raise HTTPException(status_code=404, detail="Bank not found")
        return bank
    except ValueError as e:

        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception(e)

        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.delete("/{bank_id}", status_code=204)
async def delete_bank(bank_id: int, session: Session = Depends(get_db), current_user: Dict = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.MANAGER))):
    bank_service = BankService(session)
    admin_id = current_user.get("user_id")
    try:
        bank_service.delete_bank_and_save_audit_log(admin_id, bank_id)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logging.exception(e)
        raise HTTPException(status_code=500, detail="Internal Server Error")
