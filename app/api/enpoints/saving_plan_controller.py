# app/routers/saving_plan_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.savingPlanSchema import (
    SavingPlanCreate,
    SavingPlanDeleteResponse,
    SavingPlanOptimizeResponse,
    SavingPlanOptionSave,
    SavingPlanResponse,
)
from app.service.SavingPlanService import SavingPlanService

router = APIRouter()

@router.post("/optimize", response_model=SavingPlanOptimizeResponse)
def optimize_saving(request: SavingPlanCreate, user_id: int = 6, db: Session = Depends(get_db)):

    service = SavingPlanService(db)
    try:
        result = service.optimize_plan(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{user_id}/save", response_model=SavingPlanResponse)
def save_saving_plan_option(
    user_id: int,
    request: SavingPlanOptionSave,
    db: Session = Depends(get_db),
):
    service = SavingPlanService(db)
    try:
        return service.save_plan_option(user_id, request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/history/{user_id}", response_model=list[SavingPlanResponse])
def get_history(user_id: int, db: Session = Depends(get_db)):
    service = SavingPlanService(db)
    return service.get_active_plans(user_id)

@router.get("/{user_id}", response_model=list[SavingPlanResponse])
def get_saving_plans(user_id: int, db: Session = Depends(get_db)):
    service = SavingPlanService(db)
    return service.get_active_plans(user_id)

@router.get("/{user_id}/{plan_id}", response_model=SavingPlanResponse)
def get_saving_plan_detail(
    user_id: int,
    plan_id: int,
    db: Session = Depends(get_db),
):
    service = SavingPlanService(db)
    plan = service.get_active_plan_detail(user_id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Saving plan not found")
    return plan

@router.delete("/{user_id}/{plan_id}", response_model=SavingPlanDeleteResponse)
def delete_saving_plan(
    user_id: int,
    plan_id: int,
    db: Session = Depends(get_db),
):
    service = SavingPlanService(db)
    plan = service.soft_delete_plan(user_id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Saving plan not found")

    return {
        "id": plan.id,
        "is_active": plan.is_active,
        "message": "Saving plan deleted successfully",
    }
