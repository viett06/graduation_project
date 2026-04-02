from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.api.deps import get_db
from app.schemas.bankSchema import BankResponse
from sqlalchemy.orm import Session
from app.service.bankService import BankService
from app.schemas.bankSchema import BankCreate

router = APIRouter()
@router.post("",response_model=BankResponse)
async def create_bank(data_bank: BankCreate, session: Session = Depends(get_db)):
    bank_service = BankService(session)

    try:

        bank = bank_service.create_bank(data_bank)

        return bank
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{id}",response_model=BankResponse)
async def get_detail_bank (id: int, session: Session = Depends(get_db)):
    bank_service = BankService(session)
    try:
        bank = bank_service.get_bank_by_id(id)
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

