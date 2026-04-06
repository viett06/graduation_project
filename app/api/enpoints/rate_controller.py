import logging
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.core.security.guards import require_roles
from app.core.security.rbac import RoleEnum
from app.schemas.interestRateSchema import InterestRateCreate, InterestRateResponse, InterestRateUpdate
from app.service.interestRateService import InterestRateService

router = APIRouter(prefix="/interest-rates", tags=["Interest Rates"])

@router.post("/", response_model=InterestRateResponse, status_code=status.HTTP_201_CREATED)
def create_single_rate(data: InterestRateCreate, session: Session = Depends(get_db)):
    service = InterestRateService(session)
    try:
        return service.create_interest_rate(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/bulk", response_model=List[InterestRateResponse], status_code=status.HTTP_201_CREATED)
def create_multiple_rates(data: List[InterestRateCreate], session: Session = Depends(get_db)):
    """
    Endpoint for bulk creation (Matrix input from Frontend).
    If one month fails, all changes are rolled back.
    """
    service = InterestRateService(session)
    try:
        return service.create_all_interest_rates_of_bank(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.put("/{interest_rate_id}",response_model=InterestRateResponse)
async def update_rate(interest_rate_id: int, data_update_rate: InterestRateUpdate, session: Session = Depends(get_db), current_user: Dict = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.MANAGER)),):
    interest_rate_service = InterestRateService(session)
    admin_id = current_user.get("user_id")

    try:
        rate = interest_rate_service.update_interest_rate(interest_rate_id, admin_id, data_update_rate)
        if not rate:
            raise HTTPException(status_code=404, detail="Interest Rate not found")
        return rate
    except ValueError as e:

        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception(e)

        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.delete("/{interest_rate_id}", status_code=204)
async def delete_rate(interest_rate_id: int, session: Session = Depends(get_db), current_user: Dict = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.MANAGER))):
    interest_rate_service = InterestRateService(session)
    admin_id = current_user.get("user_id")
    try:
        interest_rate_service.delete_interest_rate_and_save_audit_log(admin_id, interest_rate_id)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logging.exception(e)
        raise HTTPException(status_code=500, detail="Internal Server Error")