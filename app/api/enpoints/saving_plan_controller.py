# app/routers/saving_plan_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.savingPlanSchema import SavingPlanCreate, SavingPlanOptimizeResponse
from app.service.SavingPlanService import SavingPlanService
from app.models.saving_plans import SavingPlans

router = APIRouter()

@router.post("/optimize", response_model=SavingPlanOptimizeResponse)
def optimize_saving(request: SavingPlanCreate, user_id: int = 6, db: Session = Depends(get_db)):

    service = SavingPlanService(db)
    try:
        result = service.create_plan(user_id, request)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/history/{user_id}")
def get_history(user_id: int, db: Session = Depends(get_db)):
    plans = db.query(SavingPlans).filter(SavingPlans.user_id == user_id).all()
    return plans
