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
    monthly_extra: Optional[float] = 0                      # gửi thêm mỗi tháng cố định
    extra_schedule: Optional[List[Dict[str, Any]]] = []   # gửi thêm theo lịch: [{"month": 2, "amount": 1000000}]
    withdrawal_schedule: Optional[List[Dict[str, Any]]] = []  # rút tiền: [{"month": 3, "amount": 5000000}]
    prefer_rate: Optional[str] =  "ONLINE"              # ưu tiên lãi suất online
    risk_tolerance: Optional[str] = "low"                   # low, medium, high
    algorithm_used: Optional[str] = "dp"                  # auto, dp, greedy, monte_carlo, rule_based
    codes: Optional[List[str]] = []                    # chỉ chọn ngân hàng có mã trong list này

class SavingPlanResponse(SavingPlanBase):
    id: int
    is_active: bool
    created_at: datetime
    algorithm_used: str          # thuật toán thực tế đã dùng (sau auto)
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

class SavingPlanOptionSave(SavingPlanBase):
    plan_data: Dict[str, Any]
    algorithm_used: str = "dp"

class SavingPlanDeleteResponse(BaseModel):
    id: int
    is_active: bool
    message: str
