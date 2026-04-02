from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.interestRateSchema import InterestRateCreate, InterestRateResponse
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