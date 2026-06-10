# app/routers/saving_plan_router.py
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.core.security.dependencies import get_current_active_user
from app.schemas.savingPlanSchema import (
    SavingPlanCreate,
    SavingPlanDeleteResponse,
    SavingPlanFixedTermCreate,
    SavingPlanFixedTermResponse,
    SavingPlanOptimizeResponse,
    SavingPlanOptionSave,
    SavingPlanResponse,
)
from app.service.SavingPlanService import SavingPlanService

router = APIRouter()

@router.post("/optimize", response_model=SavingPlanOptimizeResponse)
def optimize_saving(request: SavingPlanCreate, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_active_user)):

    service = SavingPlanService(db)
    try:
        result = service.optimize_plan(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/plan-by-term", response_model=SavingPlanFixedTermResponse)
def create_fixed_term_saving_plan(
    request: SavingPlanFixedTermCreate,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    service = SavingPlanService(db)
    try:
        return service.create_fixed_term_plan(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/save", response_model=SavingPlanResponse)
def save_saving_plan_option(
    request: SavingPlanOptionSave,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):

    service = SavingPlanService(db)
    try:
        user_id = current_user.get("user_id")
        return service.save_plan_option(user_id, request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/history", response_model=list[SavingPlanResponse])
def get_history(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_active_user)):
    user_id = current_user.get("user_id")
    service = SavingPlanService(db)
    return service.get_active_plans(user_id)

@router.get("/{plan_id}", response_model=SavingPlanResponse)
def get_saving_plan_detail(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    user_id = current_user.get("user_id")
    service = SavingPlanService(db)
    plan = service.get_active_plan_detail(user_id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Saving plan not found")
    return plan

@router.delete("/{plan_id}", response_model=SavingPlanDeleteResponse)
def delete_saving_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    user_id = current_user.get("user_id")
    service = SavingPlanService(db)
    plan = service.soft_delete_plan(user_id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Saving plan not found")

    return {
        "id": plan.id,
        "is_active": plan.is_active,
        "message": "Saving plan deleted successfully",
    }
