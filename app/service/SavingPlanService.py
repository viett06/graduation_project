# app/service/SavingPlanService.py
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.repository.interestRateRepository import InterestRateRepository
from app.service.algorithm.dp_algorithm import DPOptimizer, BankProfile as DPBankProfile
from app.schemas.savingPlanSchema import (
    SavingPlanCreate,
    SavingPlanFixedTermCreate,
    SavingPlanOptionSave,
)
from app.models.saving_plans import SavingPlans
from app.repository.bank_repository import BankRepository


MAX_OPTIMIZED_PLANS = 3


class SavingPlanService:

    def __init__(self, db: Session):
        self.db = db
        self.bank_repo = BankRepository(db)
        self.rate_repo = InterestRateRepository(db)
        self.dp = None

    # def banks_rate_follow_duration_alls(self, term_month:int, codes: List[str]):
    #     banks = self.bank_repo.get_all_banks_and_rates_follow_duration_month(term_month, codes)
    #
    #     all_bank_profiles: list[BankProfile] = []
    #     # key_codes: list = []
    #     rate_of_bank_map: dict = {}
    #
    #     for bank in banks:
    #
    #         bank_profile = BankProfile()
    #
    #         if bank.code not in rate_of_bank_map:
    #             rate_of_bank_map[bank.code] = {}
    #             # key_codes.append(bank.code)
    #
    #             bank_profile.bank_id = bank.code
    #             bank_profile.code = bank.code
    #             bank_profile.name = bank.name
    #             bank_profile.rates = {}
    #             if bank.term_month == 0:
    #                 bank_profile.demand_rate = bank.interest_rates
    #             else:
    #                 bank_profile.demand_rate = 0
    #             bank_profile.transfer_fee_fixed = 0
    #             bank_profile.transfer_fee_pct = 0
    #             bank_profile.transfer_delay_days = 0
    #             all_bank_profiles.append(bank_profile)
    #
    #         rate_of_bank_map[bank.code][bank.term_month] = bank.interest_rates
    #
    #     for bank_profile in all_bank_profiles:
    #         for key, value in rate_of_bank_map.items():
    #             if bank_profile.code == key:
    #                 bank_profile.rates = value
    #                 # all_bank_profiles.append(bank_profile)
    #                 break
    #     return all_bank_profiles

    def banks_rate_follow_duration_alls(
            self,
            term_month: int,
            codes: List[str],
            channel: str = "ONLINE"
    ):
        banks = self.bank_repo.get_all_banks_and_rates_follow_duration_month(
            term_month,
            codes,
            channel
        )

        bank_profile_map: dict[str, DPBankProfile] = {}

        for bank in banks:
            bank_code = bank.code
            annual_rate = self._normalize_annual_rate(float(bank.rate))

            if bank_code not in bank_profile_map:
                bank_profile_map[bank_code] = DPBankProfile(
                    bank_id=bank_code,
                    name=bank.name,
                    rates={},
                    demand_rate=0.0,
                    transfer_fee_fixed=0.0,
                    transfer_fee_pct=0.0,
                    transfer_delay_days=0,
                )

            bank_profile = bank_profile_map[bank_code]
            if bank.term_month == 0:
                bank_profile.demand_rate = annual_rate
            else:
                bank_profile.rates[int(bank.term_month)] = annual_rate

        return [profile for profile in bank_profile_map.values() if profile.rates]

    @staticmethod
    def _normalize_annual_rate(rate: float) -> float:
        # xem xét sau kkh
        return rate / 100.0 if rate > 1 else rate

    @staticmethod
    def _limit_top_plans(result: Dict[str, Any], limit: int = MAX_OPTIMIZED_PLANS) -> Dict[str, Any]:
        """
        Giới hạn response optimize chỉ còn các phương án tốt nhất.
        Thuật toán DP có thể trả top_plans ở cả top-level và trong plan_details.
        """
        limited = dict(result or {})
        plan_details = limited.get("plan_details")

        top_plans = limited.get("top_plans")
        if not top_plans and isinstance(plan_details, dict):
            top_plans = plan_details.get("top_plans")

        if isinstance(top_plans, list):
            top_plans = top_plans[:limit]
            limited["top_plans"] = top_plans

        if isinstance(plan_details, dict):
            limited_plan_details = dict(plan_details)
            if isinstance(limited_plan_details.get("top_plans"), list):
                limited_plan_details["top_plans"] = limited_plan_details["top_plans"][:limit]
            if top_plans:
                limited_plan_details["best_plan"] = top_plans[0]
            limited["plan_details"] = limited_plan_details

        return limited

    @staticmethod
    def _normalize_algorithm_result(
            result: Dict[str, Any],
            algo: str,
            initial_amount: float,
    ) -> Dict[str, Any]:
        """
        Chuẩn hóa output của các thuật toán về format service/API dùng chung.
        DP trả chi tiết trong plan_details.best_plan/top_plans, còn các thuật toán
        khác trả final_amount/achieved_interest ở top-level.
        """
        normalized = dict(result or {})
        normalized["algorithm"] = normalized.get("algorithm", algo)

        plan_details = normalized.get("plan_details")
        best_plan = None
        if isinstance(plan_details, dict):
            best_plan = plan_details.get("best_plan")
        if best_plan is None and normalized.get("top_plans"):
            best_plan = normalized["top_plans"][0]

        if isinstance(best_plan, dict):
            normalized["final_amount"] = best_plan.get(
                "final_amount",
                normalized.get("final_amount", initial_amount)
            )
            normalized["achieved_interest"] = best_plan.get(
                "interest_earned",
                best_plan.get(
                    "achieved_interest",
                    normalized.get("achieved_interest", 0.0)
                )
            )
            normalized.setdefault("top_plans", plan_details.get("top_plans", []) if isinstance(plan_details, dict) else [])
        else:
            final_amount = normalized.get("final_amount", initial_amount)
            normalized["final_amount"] = final_amount
            normalized["achieved_interest"] = normalized.get(
                "achieved_interest",
                final_amount - initial_amount
            )
            if plan_details is not None:
                normalized["plan_details"] = plan_details
            elif "plan" in normalized:
                normalized["plan_details"] = normalized["plan"]
            else:
                normalized["plan_details"] = []

        return normalized


    def optimize_plan(self, request: SavingPlanCreate) -> Dict[str, Any]:
        # --- Chuẩn bị tham số cho thuật toán ---
        initial_amount = request.total_amount
        duration_months = request.duration_month
        prefer_rate = getattr(request, 'prefer_rate', None)
        codes = getattr(request, 'codes', [])

        choice_prefer = True
        match prefer_rate:
            case "ONLINE":
                choice_prefer = True
            case "COUNTER":
                choice_prefer = False
            case _:
                choice_prefer = True

        algo = "dp"
        dp_banks = self.banks_rate_follow_duration_alls(
            duration_months,
            codes=codes,
            channel="ONLINE" if choice_prefer else "COUNTER"
        )
        self.dp = DPOptimizer(
            banks=dp_banks,
            default_bank_id=dp_banks[0].bank_id if dp_banks else "",
        )
        result = self.dp.optimize(
            initial_amount=initial_amount,
            duration_months=duration_months,
            prefer_online=choice_prefer,
        )
        result = self._normalize_algorithm_result(result, algo, initial_amount)
        result = self._limit_top_plans(result)

        # --- Chuẩn bị response ---
        final_amount = result.get('final_amount', 0)
        is_goal_met = final_amount >= request.goal_amount
        achieved_interest = result.get('achieved_interest', final_amount - initial_amount)

        return {
            "plan_id": None,
            "final_amount": final_amount,
            "achieved_interest": achieved_interest,
            "is_goal_met": is_goal_met,
            "plan_details": result.get('plan_details', result),
            "top_plans": result.get("top_plans"),
            "algorithm_used": result.get('algorithm', algo),
            "probability_success": result.get('probability_success')
        }

    def create_plan(self, user_id: int, request: SavingPlanCreate) -> Dict[str, Any]:
        """
        Backward-compatible wrapper: hiện tại chỉ optimize và không lưu DB.
        API lưu DB nằm ở save_plan_option.
        """
        return self.optimize_plan(request)

    def create_fixed_term_plan(self, request: SavingPlanFixedTermCreate) -> Dict[str, Any]:
        amount = float(request.total_amount)
        term_month = int(request.term_month)
        channel = request.channel.upper() if request.channel else None

        if amount <= 0:
            raise ValueError("total_amount must be greater than 0")
        if term_month <= 0:
            raise ValueError("term_month must be greater than 0")

        best_rate = self.bank_repo.get_best_rate_for_term(
            term_month=term_month,
            amount=amount,
            channel=channel,
        )
        if not best_rate:
            raise ValueError("Không tìm thấy lãi suất phù hợp với kỳ hạn và số tiền đã chọn.")

        raw_rate = float(best_rate["rate"])
        annual_rate = self._normalize_annual_rate(raw_rate)
        annual_rate_pct = raw_rate if raw_rate > 1 else raw_rate * 100
        achieved_interest = round(amount * annual_rate * term_month / 12.0, 2)
        final_amount = round(amount + achieved_interest, 2)

        plan_details = {
            "strategy": "fixed_term_highest_rate",
            "summary": {
                "initial_amount": amount,
                "term_month": term_month,
                "annual_rate_pct": annual_rate_pct,
                "interest_earned": achieved_interest,
                "final_amount": final_amount,
            },
            "steps": [
                {
                    "month": 0,
                    "action": "initial",
                    "amount": amount,
                    "note": f"Số tiền ban đầu: {amount:,.0f} VNĐ",
                },
                {
                    "month": 1,
                    "action": "open_book",
                    "amount": amount,
                    "term_months": term_month,
                    "bank_id": best_rate["bank_code"],
                    "bank_name": best_rate["bank_name"],
                    "annual_rate_pct": annual_rate_pct,
                    "channel": best_rate["channel"],
                    "note": (
                        f"Gửi toàn bộ số tiền vào {best_rate['bank_name']} "
                        f"kỳ hạn {term_month} tháng với lãi suất {annual_rate_pct:.2f}%/năm"
                    ),
                },
                {
                    "month": term_month + 1,
                    "action": "mature",
                    "amount": final_amount,
                    "term_months": term_month,
                    "bank_id": best_rate["bank_code"],
                    "bank_name": best_rate["bank_name"],
                    "annual_rate_pct": annual_rate_pct,
                    "channel": best_rate["channel"],
                    "note": (
                        f"Đáo hạn: gốc {amount:,.0f} + lãi {achieved_interest:,.0f} VNĐ"
                    ),
                },
            ],
        }

        return {
            "plan_id": None,
            "bank_id": best_rate["bank_id"],
            "bank_code": best_rate["bank_code"],
            "bank_name": best_rate["bank_name"],
            "term_month": term_month,
            "channel": best_rate["channel"],
            "annual_rate_pct": annual_rate_pct,
            "total_amount": amount,
            "achieved_interest": achieved_interest,
            "final_amount": final_amount,
            "plan_details": plan_details,
        }

    def save_plan_option(self, user_id: int, request: SavingPlanOptionSave) -> SavingPlans:
        plan_data = request.plan_data
        plan = SavingPlans(
            user_id=user_id,
            name=request.name,
            total_amount=request.total_amount,
            goal_amount=request.goal_amount,
            duration_month=request.duration_month,
            plan_data=plan_data,
            algorithm_used="dp",
            notes=request.notes,
            is_active=True
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def get_active_plans(self, user_id: int) -> List[SavingPlans]:
        return (
            self.db.query(SavingPlans)
            .filter(
                SavingPlans.user_id == user_id,
                SavingPlans.is_active == True,
            )
            .order_by(SavingPlans.created_at.desc())
            .all()
        )

    def get_active_plan_detail(self, user_id: int, plan_id: int) -> SavingPlans | None:
        return (
            self.db.query(SavingPlans)
            .filter(
                SavingPlans.id == plan_id,
                SavingPlans.user_id == user_id,
                SavingPlans.is_active == True,
            )
            .first()
        )

    def soft_delete_plan(self, user_id: int, plan_id: int) -> SavingPlans | None:
        plan = self.get_active_plan_detail(user_id, plan_id)
        if not plan:
            return None

        plan.is_active = False
        self.db.commit()
        self.db.refresh(plan)
        return plan
