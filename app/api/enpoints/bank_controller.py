import logging

from fastapi import APIRouter, Depends, HTTPException, logger
from typing import List, Dict, Optional
from app.api.deps import get_db
from app.repository.bank_repository import BankRepository
from app.schemas.bankSchema import BankResponse, UpdateBank, BankCreate, UpdateBank, BankRateResponse, InterestCalculateRequest, InterestCalculateResponse
from sqlalchemy.orm import Session, session
from app.service.bankService import BankService
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

@router.get("/bank_rates",response_model=List[BankRateResponse])
async def read_bank_rates(
        term_month: int,
        amount: float = 0,
    page: int = 1,
    size: int = 10,
        session: Session = Depends(get_db),
):
    # logger.info(f"term_month={term_month}, amount={amount}, page={page}, size={size}")
    service = BankService(session)
    return service.get_banks_by_month_and_amount(term_month, amount, page, size)

@router.get("/search", response_model=List[BankResponse])
async def bank_search(name: Optional[str] = None, code: Optional[str] = None,  session: Session = Depends(get_db)):
    service = BankService(session)

    try:
        bank_searchs = service.get_bank_by_name_or_code_or_both(name, code)
        return bank_searchs
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # logging.exception(e)
        raise HTTPException(status_code=500, detail="Internal Server Error")



@router.get("/{bank_id}",response_model=BankResponse)
async def get_detail_bank (bank_id: int, session: Session = Depends(get_db)):
    bank_service = BankService(session)
    try:
        bank = bank_service.get_bank_by_id(bank_id)
        if not bank:
            raise HTTPException(status_code=404, detail="Bank not found")
        return bank
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# @router.get("/{bank_id}/terms", response_model=List[int])
# async def get_bank_terms(bank_id: int, session: Session = Depends(get_db)):
#     service = BankService(session)
#     return service.get_bank_terms(bank_id)

@router.post("/calculate", response_model=InterestCalculateResponse)
async def calculate_interest(
    data: InterestCalculateRequest,
    session: Session = Depends(get_db)
):

    service = BankService(session)
    try:
        return service.calculate_interest(data)
    except ValueError as e:
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


@router.get("/bank_rates/{bank_id}", response_model=BankResponse)
async def get_rates_bank(bank_id: int, session: Session = Depends(get_db)):
    bank_service = BankService(session)
    try:
        bank = bank_service.get_rates_of_bank(bank_id)
        if not bank:
            raise HTTPException(status_code=404, detail="Bank not found")
        return bank
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")




