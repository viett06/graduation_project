# app/service/SavingPlanService.py
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.repository.interestRateRepository import InterestRateRepository
from app.service.algorithm.dp_algorithm import DPOptimizer, BankProfile as DPBankProfile
from app.service.algorithm.greedy_algorithm import GreedyAlgorithm
from app.service.algorithm.monte_carlo import MonteCarloAlgorithm
from app.service.algorithm.rule_based import RuleBasedAlgorithm
from app.schemas.savingPlanSchema import SavingPlanCreate
from app.models.saving_plans import SavingPlans
from app.repository.bank_repository import BankRepository


class SavingPlanService:

    def __init__(self, db: Session):
        self.db = db
        self.bank_repo = BankRepository(db)
        self.rate_repo = InterestRateRepository(db)
        self.dp = None
        self.greedy = GreedyAlgorithm(self.rate_repo)
        self.mc = MonteCarloAlgorithm(self.rate_repo)
        self.rule = RuleBasedAlgorithm(self.rate_repo)

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


    def create_plan(self, user_id: int, request: SavingPlanCreate) -> Dict[str, Any]:
        # --- Chuẩn bị tham số cho thuật toán ---
        initial_amount = request.total_amount
        duration_months = request.duration_month
        monthly_extra = getattr(request, 'monthly_extra', 0) or 0
        extra_schedule = getattr(request, 'extra_schedule', None)
        withdrawal_schedule = getattr(request, 'withdrawal_schedule', None)
        prefer_rate = getattr(request, 'prefer_rate', None)
        risk_tolerance = getattr(request, 'risk_tolerance', 'low')
        codes = getattr(request, 'codes', [])

        choice_prefer = True
        match prefer_rate:
            case "ONLINE":
                choice_prefer = True
            case "COUNTER":
                choice_prefer = False
            case _:
                choice_prefer = True

        # --- Chọn thuật toán ---
        algo = (request.algorithm_used or "auto").lower()
        if algo == "auto":
            # Heuristic tự động chọn
            if (withdrawal_schedule and len(withdrawal_schedule) > 0) or \
               (extra_schedule and len(extra_schedule) > 1):
                algo = "dp"
            elif risk_tolerance != "low":
                algo = "monte_carlo"
            else:
                algo = "greedy"

        # --- Gọi đúng thuật toán ---
        if algo == "dp":
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
                initial_amount, duration_months,
                monthly_extra, extra_schedule,
                withdrawal_schedule, choice_prefer
            )
        elif algo == "greedy":
            result = self.greedy.optimize(
                initial_amount, duration_months,
                monthly_extra, extra_schedule,
                withdrawal_schedule, choice_prefer
            )
        elif algo == "monte_carlo":
            mc_result = self.mc.simulate(
                initial_amount, duration_months,
                monthly_extra, extra_schedule,
                withdrawal_schedule, choice_prefer,
                num_simulations=500
            )
            # Tính xác suất đạt goal_amount
            target_total = request.goal_amount
            # Giả sử mc_result có chứa danh sách final_balances (cần cập nhật trong monte_carlo)
            # Ở đây tạm dùng expected_final và giả lập probability
            probability = 0.75  # placeholder: thực tế nên tính từ phân phối
            result = {
                "algorithm": "monte_carlo",
                "final_amount": mc_result.get('expected_final', initial_amount),
                "achieved_interest": mc_result.get('expected_final', initial_amount) - initial_amount,
                "probability_success": probability,
                "plan_details": mc_result
            }
        else:  # rule_based
            result = self.rule.recommend(
                initial_amount, duration_months,
                monthly_extra, extra_schedule,
                withdrawal_schedule, choice_prefer
            )
            # Tính lãi đạt được
            if 'final_amount' in result:
                result['achieved_interest'] = result['final_amount'] - initial_amount
                if monthly_extra:
                    total_extra = monthly_extra * duration_months
                    result['achieved_interest'] -= total_extra
            else:
                result['final_amount'] = initial_amount
                result['achieved_interest'] = 0

        result = self._normalize_algorithm_result(result, algo, initial_amount)

        # --- Lưu kế hoạch vào database ---
        plan = SavingPlans(
            user_id=user_id,
            name=request.name,
            total_amount=initial_amount,
            goal_amount=request.goal_amount,
            duration_month=duration_months,
            plan_data=result,
            algorithm_used=result.get('algorithm', algo),
            notes=request.notes,
            is_active=True
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)

        # --- Chuẩn bị response ---
        final_amount = result.get('final_amount', 0)
        is_goal_met = final_amount >= request.goal_amount
        achieved_interest = result.get('achieved_interest', final_amount - initial_amount)

        return {
            "plan_id": plan.id,
            "final_amount": final_amount,
            "achieved_interest": achieved_interest,
            "is_goal_met": is_goal_met,
            "plan_details": result.get('plan_details', result),
            "top_plans": result.get("top_plans"),
            "algorithm_used": result.get('algorithm', algo),
            "probability_success": result.get('probability_success')
        }
