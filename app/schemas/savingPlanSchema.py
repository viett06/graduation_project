# app/schemas/savingPlanSchema.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any

class SavingPlanBase(BaseModel):
    name: str
    duration_month: int
    total_amount: float          # số tiền ban đầu
    goal_amount: float          # mục tiêu tổng tiền cuối kỳ
    notes: Optional[str] = None

class SavingPlanCreate(SavingPlanBase):
    prefer_rate: Optional[str] =  "ONLINE"              # ưu tiên lãi suất online
    codes: Optional[List[str]] = []                    # chỉ chọn ngân hàng có mã trong list này

class SavingPlanResponse(SavingPlanBase):
    id: int
    is_active: bool
    created_at: datetime
    algorithm_used: str
    plan_data: Dict[str, Any] | List[Dict[str, Any]]
    model_config = ConfigDict(from_attributes=True)

class SavingPlanOptimizeResponse(BaseModel):
    plan_id: Optional[int] = None
    final_amount: float
    achieved_interest: float
    is_goal_met: bool
    plan_details: Dict[str, Any] | List[Dict[str, Any]]
    top_plans: Optional[List[Dict[str, Any]]] = None
    algorithm_used: str
    probability_success: Optional[float] = None

class SavingPlanFixedTermCreate(BaseModel):
    total_amount: float
    term_month: int
    channel: Optional[str] = None

class SavingPlanFixedTermResponse(BaseModel):
    plan_id: Optional[int] = None
    bank_id: int
    bank_code: str
    bank_name: str
    term_month: int
    channel: str
    annual_rate_pct: float
    total_amount: float
    achieved_interest: float
    final_amount: float
    plan_details: Dict[str, Any]

class SavingPlanOptionSave(SavingPlanBase):
    plan_data: Dict[str, Any]

class SavingPlanDeleteResponse(BaseModel):
    id: int
    is_active: bool
    message: str
