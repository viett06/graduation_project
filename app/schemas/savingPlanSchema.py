# app/schemas/savingPlanSchema.py
import json
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional, Dict, Any


def parse_plan_data(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("plan_data must be a valid JSON object or list") from exc
    return value

class SavingPlanBase(BaseModel):
    name: str
    duration_month: int
    total_amount: float          # số tiền ban đầu
    goal_amount: float          # mục tiêu tổng tiền cuối kỳ
    notes: Optional[str] = None

class SavingPlanCreate(SavingPlanBase):
    total_amount: float = Field(ge=1_000_000)
    prefer_rate: Optional[str] =  "ONLINE"              # ưu tiên lãi suất online
    codes: Optional[List[str]] = []                    # chỉ chọn ngân hàng có mã trong list này

class SavingPlanResponse(SavingPlanBase):
    id: int
    is_active: bool
    created_at: datetime
    algorithm_used: str
    plan_data: Dict[str, Any] | List[Dict[str, Any]]
    model_config = ConfigDict(from_attributes=True)

    @field_validator("plan_data", mode="before")
    @classmethod
    def validate_plan_data(cls, value: Any) -> Any:
        return parse_plan_data(value)

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
    total_amount: float = Field(ge=1_000_000)
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

    @field_validator("plan_data", mode="before")
    @classmethod
    def validate_plan_data(cls, value: Any) -> Any:
        return parse_plan_data(value)

class SavingPlanDeleteResponse(BaseModel):
    id: int
    is_active: bool
    message: str
