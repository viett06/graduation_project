"""
dp_algorithm.py — Tối ưu gửi tiết kiệm đa ngân hàng, đa sổ song song (v3)

Cải tiến so với v2:
  - Hỗ trợ N ngân hàng với ma trận lãi suất riêng biệt
  - Mô hình phí chuyển khoản liên ngân hàng (fixed + % amount)
  - Thời gian trễ (delay days) khi nhảy ngân hàng → tiền nằm chờ mất lãi
  - Tự động xét chiến lược: 1 ngân hàng cố định vs tái tục / nhảy ngân hàng
  - Tất toán cuối kỳ với đánh giá lợi / hại so với lãi kỳ hạn mới
  - DP + beam search trên không gian (bank_id, cash, tuple sổ đang mở)
  - Output: Top 3 lộ trình chi tiết theo tháng
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
# from app.schemas.bankSchema import BankProfile


# ---------------------------------------------------------------------------
# Kiểu dữ liệu ngân hàng & lãi suất
# ---------------------------------------------------------------------------

@dataclass
class BankProfile:
    bank_id: str
    name: str
    rates: Dict[int, float]          # {term_months: annual_rate}
    demand_rate: float = 0.0         # Lãi KKH (mặc định 0.5%/năm)
    transfer_fee_fixed: float = 0.0  # Phí chuyển khoản cố định (VNĐ)
    transfer_fee_pct: float = 0.0    # Phí chuyển khoản theo % số tiền
    transfer_delay_days: int = 0     # Số ngày tiền nằm chờ khi nhảy ngân hàng




# Bước lượng tử hóa tiền khi chạy exact search. Exact tuyệt đối đến từng đồng
# thường không thực tế vì số trạng thái tăng rất nhanh.
DEFAULT_ALLOCATION_STEP = 1_000_000


# ---------------------------------------------------------------------------
# Cấu trúc dữ liệu
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Book:
    """Một sổ tiết kiệm đang mở (immutable để dùng làm key DP)."""
    principal: float
    term: int
    annual_rate: float
    demand_rate: float
    open_month: int
    close_month: int
    bank_id: str
    bank_name: str

    def interest_full(self) -> float:
        return self.principal * self.annual_rate * (self.term / 12.0)

    def value_at_maturity(self) -> float:
        return self.principal + self.interest_full()

    def kkh_interest(self, months_held: int) -> float:
        if months_held <= 0:
            return 0.0
        return self.principal * self.demand_rate * (months_held / 12.0)

    def value_if_closed_early(self, current_month: int) -> float:
        months_held = current_month - self.open_month
        return self.principal + self.kkh_interest(months_held)


@dataclass
class Step:
    """Một hành động trong kế hoạch."""
    month: int
    action: str
    amount: float
    term: Optional[int] = None
    bank_id: Optional[str] = None
    bank_name: Optional[str] = None
    rate_pct: Optional[float] = None
    fee: Optional[float] = None
    note: Optional[str] = None


# Hành động
ACTION_INITIAL       = "initial"
ACTION_MATURE        = "mature"
ACTION_OPEN          = "open_book"
ACTION_HOLD_CASH     = "hold_cash"
ACTION_EARLY_CLOSE   = "early_close"
ACTION_KKH_INTEREST  = "kkh_interest"
ACTION_TRANSFER_FEE  = "transfer_fee"
ACTION_TRANSFER_WAIT = "transfer_wait"
ACTION_FINAL         = "final_balance"

State = Tuple[float, Tuple[Book, ...]]


def _r(x: float) -> float:
    return round(x, 2)


# ---------------------------------------------------------------------------
# Sinh tổ hợp phân chia tiền
# ---------------------------------------------------------------------------

def _allocations(
    cash: float,
    n: int,
    min_deposit: float,
    allocation_step: float = DEFAULT_ALLOCATION_STEP,
    exact: bool = False,
) -> List[Tuple[float, ...]]:
    # if n == 1:
    #     return [(cash,)] if cash >= min_deposit else []
    #
    # if not exact:
    #     results: List[Tuple[float, ...]] = []
    #     if n == 2:
    #         for f in (0.25, 0.5, 0.75):
    #             a = _r(cash * f)
    #             b = _r(cash - a)
    #             if a >= min_deposit and b >= min_deposit:
    #                 results.append((a, b))
    #     elif n == 3:
    #         splits = {
    #             (1 / 3, 1 / 3, 1 / 3),
    #             (0.25, 0.25, 0.5),
    #             (0.25, 0.5, 0.25),
    #             (0.5, 0.25, 0.25),
    #         }
    #         for f1, f2, _ in splits:
    #             a = _r(cash * f1)
    #             b = _r(cash * f2)
    #             c = _r(cash - a - b)
    #             if a >= min_deposit and b >= min_deposit and c >= min_deposit:
    #                 results.append((a, b, c))
    #     return list(dict.fromkeys(results))

    if n == 1:
        return [(cash,)] if cash >= min_deposit else []

    if not exact:
        results: List[Tuple[float, ...]] = []

        if n == 2:
            ratios = [0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9]

            for f in ratios:
                a = _r(cash * f)
                b = _r(cash - a)
                if a >= min_deposit and b >= min_deposit:
                    results.append((a, b))

        elif n == 3:
            ratio_patterns = [
                (0.1, 0.2, 0.7),
                (0.1, 0.3, 0.6),
                (0.1, 0.4, 0.5),
                (0.2, 0.2, 0.6),
                (0.2, 0.3, 0.5),
                (0.2, 0.4, 0.4),
                (0.25, 0.25, 0.5),
                (1 / 3, 1 / 3, 1 / 3),
            ]

            for pattern in ratio_patterns:
                for f1, f2, f3 in set(itertools.permutations(pattern)):
                    a = _r(cash * f1)
                    b = _r(cash * f2)
                    c = _r(cash - a - b)

                    if a >= min_deposit and b >= min_deposit and c >= min_deposit:
                        results.append((a, b, c))

        return list(dict.fromkeys(results))

    # Exact mode: chia theo bước allocation_step. Với step nhỏ như 1 triệu,
    # nhánh này có thể sinh rất nhiều candidate và chỉ nên chạy offline.
    step = max(float(allocation_step), 1.0)
    min_units = int((min_deposit + step - 1) // step)
    total_units = int(cash // step)
    remainder = _r(cash - total_units * step)
    results: List[Tuple[float, ...]] = []

    if total_units < min_units * n:
        return results

    if n == 2:
        for u1 in range(min_units, total_units - min_units + 1):
            a = _r(u1 * step)
            b = _r(cash - a)
            if a >= min_deposit and b >= min_deposit:
                results.append((a, b))
    elif n == 3:
        for u1 in range(min_units, total_units - 2 * min_units + 1):
            for u2 in range(min_units, total_units - u1 - min_units + 1):
                a = _r(u1 * step)
                b = _r(u2 * step)
                c = _r(cash - a - b)
                if a >= min_deposit and b >= min_deposit and c >= min_deposit:
                    results.append((a, b, c))

    if remainder > 0:
        results = list(dict.fromkeys(tuple(_r(v) for v in item) for item in results))
    return results

def _generate_multi_book_plans(
    cash: float,
    active_books: Tuple[Book, ...],
    month: int,
    months_remaining: int,
    banks: List[BankProfile],
    current_bank_id: str,
    max_books: int,
    min_deposit: float,
    allocation_step: float = DEFAULT_ALLOCATION_STEP,
    exact: bool = False,
    max_open_options: int = 12,
    max_plans_per_state: int = 120,
    max_new_books_per_step: int = 2,
) -> List[Tuple[Tuple[Book, ...], float, float, List[Step]]]:
    """
    Sinh tất cả cách phân chia cash vào 1..n sổ mới.
    Mỗi sổ có thể ở bất kỳ ngân hàng nào (tự động tính phí chuyển khoản).
    Returns: List of (new_books_tuple, remaining_cash, total_fee, steps)
    """
    # slots = số sổ mở tối đa cùng lúc - số sổ đang mở khả dụng
    slots = max_books - len(active_books)
    if slots <= 0 or cash < min_deposit:
        return []

    results = []

    # Tạo danh sách (bank, term, rate) khả dụng
    options = []
    # lấy tất cả kỳ hạn và lãi suất của tất cả các ngân hàng nằm tỏng khoảng thời hạn cho phép
    for bank in banks:
        for term, rate in bank.rates.items():
            if term <= months_remaining:
                options.append((bank, term, rate))

    # if not exact:
    #     options.sort(key=lambda x: (x[2] * x[1] / 12.0, x[2], x[1]), reverse=True)
    #     options = options[:max_open_options]

    if not exact:
        # sort theo lãi tuyệt đối trên toàn kỳ, không phải tích
        # Đảm bảo kỳ hạn = duration luôn có mặt nếu tồn tại
        # sắp xếp giảm dần theo tháng
        options.sort(key=lambda x: x[2], reverse=True)

        # Đảm bảo luôn giữ lại option gửi toàn kỳ (term == months_remaining)
        # full_term_options = [o for o in options if o[1] == months_remaining]
        # other_options = [o for o in options if o[1] != months_remaining]
        # options = full_term_options + other_options[:max(0, max_open_options - len(full_term_options))]

        if not exact:
            # - Giữ đa dạng kỳ hạn để tối ưu thanh khoản và tái đầu tư
            full_term_options = [
                o for o in options
                if o[1] == months_remaining
            ]

            short_term_options = [
                o for o in options
                if o[1] <= max(1, months_remaining // 3)
            ]

            medium_term_options = [
                o for o in options
                if max(1, months_remaining // 3) < o[1] < months_remaining
            ]

            # Sort từng nhóm theo lãi suất giảm dần
            full_term_options.sort(key=lambda x: x[2], reverse=True)
            medium_term_options.sort(key=lambda x: x[2], reverse=True)
            short_term_options.sort(key=lambda x: x[2], reverse=True)

            selected = []

            # Chia quota cho từng nhóm
            full_quota = max(1, int(max_open_options * 0.4))
            medium_quota = max(1, int(max_open_options * 0.4))
            short_quota = max(1, max_open_options - full_quota - medium_quota)

            selected.extend(full_term_options[:full_quota])
            selected.extend(medium_term_options[:medium_quota])
            selected.extend(short_term_options[:short_quota])

            # Nếu chưa đủ max_open_options thì bù bằng các option tốt nhất còn lại
            selected_keys = {
                (bank.bank_id, term)
                for bank, term, rate in selected
            }

            remaining_options = [
                o for o in options
                if (o[0].bank_id, o[1]) not in selected_keys
            ]

            # sắp xếp các options chưa được lấy giảm dần theo rate
            remaining_options.sort(key=lambda x: x[2], reverse=True)

            # lấy max_options là 12
            for o in remaining_options:
                if len(selected) >= max_open_options:
                    break
                selected.append(o)

            # Deduplicate lần cuối
            # Tự động remove duplicate.
            dedup = {}
            for bank, term, rate in selected:
                dedup[(bank.bank_id, term)] = (bank, term, rate)

            options = list(dedup.values())[:max_open_options]

    n_limit = slots if exact else min(slots, max_new_books_per_step)
    # sinh tổ hợp cách chia ra tất cả các state
    for n_new in range(1, n_limit + 1):
        for combo in itertools.combinations(options, n_new):
            for allocation in _allocations(cash, n_new, min_deposit, allocation_step, exact):
                new_books: List[Book] = []
                open_steps: List[Step] = []
                total_fee = 0.0
                total_allocated = sum(allocation)
                remaining_cash = _r(cash - total_allocated)
                valid = True

                for (bank, term, rate), principal in zip(combo, allocation):
                    if principal < min_deposit:
                        valid = False
                        break

                    # Phí chuyển khoản nếu khác ngân hàng hiện tại
                    fee = 0.0
                    if bank.bank_id != current_bank_id:
                        fee = _r(bank.transfer_fee_fixed
                                 + principal * bank.transfer_fee_pct)
                        if fee > 0:
                            total_fee += fee
                            open_steps.append(Step(
                                month=month,
                                action=ACTION_TRANSFER_FEE,
                                amount=fee,
                                bank_id=bank.bank_id,
                                bank_name=bank.name,
                                note=f"Phí chuyển khoản sang {bank.name}"
                            ))

                    # Thời gian trễ: mất lãi KKH trong delay_days
                    delay_interest_loss = 0.0
                    if bank.bank_id != current_bank_id and bank.transfer_delay_days > 0:
                        delay_months = bank.transfer_delay_days / 30.0
                        delay_interest_loss = _r(
                            principal * bank.demand_rate * delay_months
                        )
                        if delay_interest_loss > 0:
                            open_steps.append(Step(
                                month=month,
                                action=ACTION_TRANSFER_WAIT,
                                amount=delay_interest_loss,
                                bank_id=bank.bank_id,
                                bank_name=bank.name,
                                note=(f"Mất lãi {delay_interest_loss:,.0f} VNĐ"
                                      f" do chờ {bank.transfer_delay_days} ngày")
                            ))

                    effective_principal = _r(principal - fee - delay_interest_loss)
                    if effective_principal < min_deposit:
                        valid = False
                        break

                    b = Book(
                        principal=effective_principal,
                        term=term,
                        annual_rate=rate,
                        demand_rate=bank.demand_rate,
                        open_month=month,
                        close_month=month + term,
                        bank_id=bank.bank_id,
                        bank_name=bank.name,
                    )
                    new_books.append(b)
                    projected_interest = _r(effective_principal * rate * term / 12)
                    open_steps.append(Step(
                        month=month,
                        action=ACTION_OPEN,
                        amount=effective_principal,
                        term=term,
                        bank_id=bank.bank_id,
                        bank_name=bank.name,
                        rate_pct=round(rate * 100, 3),
                        note=(f"Kỳ hạn {term}T @ {rate*100:.2f}%/năm"
                              f" tại {bank.name}"
                              f", đáo hạn T{month + term}"
                              f", lãi dự kiến {projected_interest:,.0f} VNĐ")
                    ))

                if not valid:
                    continue

                if remaining_cash > 0:
                    open_steps.append(Step(
                        month=month,
                        action=ACTION_HOLD_CASH,
                        amount=remaining_cash,
                        note="Cash còn lại hưởng KKH"
                    ))

                results.append((tuple(new_books), remaining_cash, total_fee, open_steps))

                if not exact and len(results) >= max_plans_per_state * 4:
                    break
            if not exact and len(results) >= max_plans_per_state * 4:
                break
        if not exact and len(results) >= max_plans_per_state * 4:
            break

    if not exact and len(results) > max_plans_per_state:
        def plan_score(item: Tuple[Tuple[Book, ...], float, float, List[Step]]) -> float:
            books, remaining_cash, total_fee, _ = item
            future_interest = sum(book.interest_full() for book in books)
            best_demand = max((bank.demand_rate for bank in banks), default=0.0)
            cash_growth = remaining_cash * best_demand * max(months_remaining, 0) / 12.0
            return future_interest + cash_growth - total_fee

        results.sort(key=plan_score, reverse=True)
        results = results[:max_plans_per_state]

    return results

class DPOptimizer:
    """
    Tối ưu kế hoạch gửi tiết kiệm đa ngân hàng bằng DP + Beam Search.

    Thứ tự xử lý mỗi tháng:
      1. Nhận gốc + lãi từ sổ đáo hạn → cash
      2. Tính lãi KKH trên cash
      3. Sinh TẤT CẢ lựa chọn:
         a. Giữ cash
         b. Mở 1..m_max sổ tại bất kỳ ngân hàng nào (tự tính phí / trễ)
    """

    def __init__(
        self,
        banks: Optional[List[BankProfile]] = None,
        default_bank_id: str = "VCB",
        max_books_open: int = 3,
        top_k_beam: int = 1000,
        min_deposit: float = 1_000_000,
        top_n_results: int = 3,
        exact: bool = False,
        allocation_step: float = DEFAULT_ALLOCATION_STEP,
        max_candidate_states: Optional[int] = None,
        max_open_options: int = 12,
        max_plans_per_state: int = 120,
        max_new_books_per_step: int = 2,
    ):
        self.banks = banks or []
        self._normalize_bank_rates()
        self.bank_map: Dict[str, BankProfile] = {b.bank_id: b for b in self.banks}
        self.default_bank_id = default_bank_id
        self.max_books = max_books_open
        self.top_k = top_k_beam
        self.min_deposit = min_deposit
        self.top_n = top_n_results
        self.exact = exact
        self.allocation_step = allocation_step
        self.max_candidate_states = max_candidate_states or max(self.top_k * 10, self.top_k)
        self.max_open_options = max_open_options
        self.max_plans_per_state = max_plans_per_state
        self.max_new_books_per_step = max_new_books_per_step

    def _normalize_bank_rates(self) -> None:
        for bank in self.banks:
            bank.demand_rate = self._normalize_demand_rate(bank.demand_rate)
            bank.rates = {
                int(term): self._normalize_term_rate(float(rate))
                for term, rate in bank.rates.items()
                if int(term) > 0
            }

    @staticmethod
    def _normalize_term_rate(rate: float) -> float:
        return rate / 100.0 if rate > 1 else rate

    @staticmethod
    def _normalize_demand_rate(rate: float) -> float:
        # DB thường lưu KKH dạng phần trăm như 0.5 nghĩa là 0.5%/năm.
        # Nếu giữ nguyên 0.5 thì output sẽ thành 50%/năm.
        if rate > 0.2:
            return rate / 100.0
        return rate
    

    # ── Public API ──────────────────────────────────────────────────────

    def optimize(
        self,
        initial_amount: float,
        duration_months: int,
        prefer_online: bool = True,
    ) -> Dict:
        """
        Tìm top 3 kế hoạch gửi tiết kiệm tối ưu (đa ngân hàng).

        Args:
            initial_amount:      Số tiền ban đầu (VNĐ)
            duration_months:     Tổng thời gian (tháng)
        """
        if not self.banks:
            return {
                "algorithm": "dp",
                "final_amount": initial_amount,
                "achieved_interest": 0.0,
                "plan_details": [],
                "error": "There is no suitable bank interest rate data to run DP."
            }

        baseline_results = self._baseline_single_deposit(
            initial_amount=initial_amount,
            duration_months=duration_months,
            enabled=True,
        )

        init_state: State = (_r(initial_amount), ())
        states: Dict[State, Tuple[float, List[Step]]] = {
            init_state: (
                0.0,
                [Step(month=0, action=ACTION_INITIAL, amount=initial_amount,
                      note=f"Số tiền ban đầu: {initial_amount:,.0f} VNĐ")]
            )
        }

        final_results: List[Tuple[float, float, List[Step]]] = []

        # for month in range(1, duration_months + 1):
        #     is_last = (month == duration_months)
        # duyệt qua từng tháng
        for month in range(1, duration_months + 2):
            is_last = (month == duration_months + 1)

            if is_last:
                for (cash, books), (accrued_interest, steps) in states.items():
                    final_cash, final_interest, close_steps = self._close_all(
                        month=month,
                        cash=cash,
                        books=books,
                        base_interest=accrued_interest,
                    )
                    all_steps = steps + close_steps
                    all_steps.append(Step(
                        month=month,
                        action=ACTION_FINAL,
                        amount=_r(final_cash),
                        note=f"Tổng lãi ròng: {_r(final_interest):,.0f} VNĐ"
                    ))
                    final_results.append((final_cash, final_interest, all_steps))
                continue

            # months_remaining = duration_months - month
            # số tháng khả dụng để mở sổ mới
            months_remaining = duration_months - month + 1

            # key là tuple đại diện cho trạng thái tài chính mới, value là tổng lãi luỹ kế đạt được tính tới thời điểm này và danh sách các bước đã thực hiện để đạt được trạng thái đó.
            next_states: Dict[State, Tuple[float, List[Step]]] = {}

            # for (cash, books), (accrued_interest, steps) in states.items():
            #     # Xác định ngân hàng hiện tại (theo sổ cuối cùng mở)
            #     current_bank_id = self._infer_current_bank(books)

            #     for new_state, delta_interest, new_steps in self._expand(
            #         month=month,
            #         cash=cash,
            #         books=books,
            #         extra=extra,
            #         withdraw=withdraw,
            #         months_remaining=months_remaining,
            #         is_last=is_last,
            #         current_bank_id=current_bank_id,
            #     ):
            #         new_cash, new_books = new_state
            #         total_interest = accrued_interest + delta_interest
            #         full_steps = steps + new_steps
            #
            #         if is_last:
            #             final_cash, final_interest, close_steps = self._close_all(
            #                 month=month,
            #                 cash=new_cash,
            #                 books=new_books,
            #                 base_interest=total_interest,
            #             )
            #             all_steps = full_steps + close_steps
            #             all_steps.append(Step(
            #                 month=month,
            #                 action=ACTION_FINAL,
            #                 amount=_r(final_cash),
            #                 note=f"Tổng lãi ròng: {_r(final_interest):,.0f} VNĐ"
            #             ))
            #             final_results.append((final_cash, final_interest, all_steps))
            #         else:
            #             existing = next_states.get(new_state)
            #             if existing is None or total_interest > existing[0]:
            #                 next_states[new_state] = (total_interest, full_steps)
            #
            # if not is_last:
            #     states = self._beam_prune(next_states)
            #     if not states:
            #         return {"error": "Không tìm được kế hoạch khả thi. Kiểm tra lại lịch rút tiền."}

            for (cash, books), (accrued_interest, steps) in states.items():

                # Xác định ngân hàng hiện tại từ sổ gần nhất đang mở.
                current_bank_id = self._infer_current_bank(books)

                # outcomes nhận danh sách các trạng thái mới từ hàm _expand
                outcomes = self._expand(
                    month=month,
                    cash=cash,
                    books=books,
                    months_remaining=months_remaining,
                    is_last=is_last,
                    current_bank_id=current_bank_id,
                )

                for new_state, delta_interest, new_steps in outcomes:
                    new_cash, new_books = new_state
                    total_interest = accrued_interest + delta_interest
                    full_steps = steps + new_steps

                    # Không làm tròn/làm mịn state tài chính ở đây. Việc bucket
                    # principal của sổ có thể tự tạo thêm hoặc làm mất tiền,
                    # khiến final_amount lệch khỏi interest_earned.
                    state_key = (new_cash, new_books)
                    existing = next_states.get(state_key)
                    if existing is None or total_interest > existing[0]:
                        next_states[state_key] = (total_interest, full_steps)

                if (
                    not self.exact
                    and self.max_candidate_states
                    and len(next_states) > self.max_candidate_states
                ):
                    next_states = self._beam_prune(next_states, months_remaining)

            if not is_last:
                if self.exact:
                    states = next_states
                else:
                    # Beam Search chỉ dùng cho chế độ nhanh, không đảm bảo tối ưu tuyệt đối.
                    states = self._beam_prune(next_states, months_remaining)
                if not states:
                    return {
                        "algorithm": "dp",
                        "final_amount": initial_amount,
                        "achieved_interest": 0.0,
                        "plan_details": [],
                        "error": "Không tìm được kế hoạch khả thi."
                    }

        final_results, benchmark_result, selection_mode = self._rank_results_against_baseline(
            dp_results=final_results,
            baseline_results=baseline_results,
        )
        top = final_results[:self.top_n]

        top_plans = [
            self._format_result(
                rank=i + 1,
                final_cash=fc,
                interest_earned=ie,
                steps=st,
                initial_amount=initial_amount,
            )
            for i, (fc, ie, st) in enumerate(top)
        ]
        if not top_plans:
            return {
                "algorithm": "dp",
                "final_amount": initial_amount,
                "achieved_interest": 0.0,
                "plan_details": [],
                "error": "Không tìm được kế hoạch khả thi."
            }

        best_plan = top_plans[0]
        benchmark_plan = None
        if benchmark_result is not None:
            benchmark_plan = self._format_result(
                rank=0,
                final_cash=benchmark_result[0],
                interest_earned=benchmark_result[1],
                steps=benchmark_result[2],
                initial_amount=initial_amount,
            )
        return {
            "algorithm": "dp",
            "mode": "exact" if self.exact else "beam",
            "allocation_step": self.allocation_step,
            "beam_width": None if self.exact else self.top_k,
            "max_open_options": None if self.exact else self.max_open_options,
            "max_plans_per_state": None if self.exact else self.max_plans_per_state,
            "selection_mode": selection_mode,
            "single_deposit_benchmark": benchmark_plan,
            "final_amount": best_plan["final_amount"],
            "achieved_interest": best_plan["interest_earned"],
            "plan_details": {
                "best_plan": best_plan,
                "top_plans": top_plans,
                "selection_mode": selection_mode,
                "single_deposit_benchmark": benchmark_plan,
            },
            "top_plans": top_plans,
        }

    def _baseline_single_deposit(
        self,
        initial_amount: float,
        duration_months: int,
        enabled: bool = True,
    ) -> List[Tuple[float, float, List[Step]]]:
        """
        Sinh các phương án baseline: gửi toàn bộ tiền ban đầu vào một sổ
        lãi đơn, không tái tục, không chia tiền.

        Baseline chỉ đúng khi bài toán không có dòng tiền phát sinh. Nếu có
        gửi thêm/rút tiền, việc đưa baseline này vào top plans sẽ so sánh sai
        với net contribution của bài toán chính.
        """
        if not enabled or initial_amount < self.min_deposit or duration_months <= 0:
            return []

        best_choice: Optional[Tuple[BankProfile, int, float]] = None

        for bank in self.banks:
            for term, rate in bank.rates.items():
                if term > duration_months:
                    continue
                if best_choice is None:
                    best_choice = (bank, term, rate)
                    continue

                _, best_term, best_rate = best_choice
                if (rate, term) > (best_rate, best_term):
                    best_choice = (bank, term, rate)

        if best_choice is None:
            return []

        bank, term, rate = best_choice
        interest = _r(initial_amount * rate * term / 12.0)
        final_cash = _r(initial_amount + interest)
        steps = [
            Step(
                month=0,
                action=ACTION_INITIAL,
                amount=initial_amount,
                note=f"Số tiền ban đầu: {initial_amount:,.0f} VNĐ",
            ),
            Step(
                month=1,
                action=ACTION_OPEN,
                amount=initial_amount,
                term=term,
                bank_id=bank.bank_id,
                bank_name=bank.name,
                rate_pct=round(rate * 100, 3),
                note=(
                    f"Benchmark: gửi toàn bộ một lần vào kỳ hạn có lãi suất cao nhất "
                    f"{term}T @ {rate*100:.2f}%/năm tại {bank.name}"
                ),
            ),
            Step(
                month=1 + term,
                action=ACTION_MATURE,
                amount=final_cash,
                term=term,
                bank_id=bank.bank_id,
                bank_name=bank.name,
                rate_pct=round(rate * 100, 3),
                note=f"Đáo hạn benchmark: gốc {initial_amount:,.0f} + lãi {interest:,.0f} VNĐ",
            ),
            Step(
                month=duration_months + 1,
                action=ACTION_FINAL,
                amount=final_cash,
                note=f"Tổng lãi benchmark: {interest:,.0f} VNĐ",
            ),
        ]
        return [(final_cash, interest, steps)]

    def _rank_results_against_baseline(
        self,
        dp_results: List[Tuple[float, float, List[Step]]],
        baseline_results: List[Tuple[float, float, List[Step]]],
    ) -> Tuple[
        List[Tuple[float, float, List[Step]]],
        Optional[Tuple[float, float, List[Step]]],
        str,
    ]:
        """
        Xếp hạng kết quả theo benchmark gửi một lần.

        Nếu có phương án DP vượt benchmark kỳ hạn lãi suất cao nhất thì trả về
        các phương án vượt benchmark. Nếu không có, fallback về top cao nhất
        sau khi hợp nhất DP với benchmark. Bên gọi vẫn cắt theo self.top_n
        (mặc định top 3).
        """
        def rank_key(item: Tuple[float, float, List[Step]]) -> Tuple[float, float]:
            return (item[0], item[1])

        benchmark = baseline_results[0] if baseline_results else None
        if benchmark is not None:
            better_than_benchmark = [
                result
                for result in dp_results
                if rank_key(result) > rank_key(benchmark)
            ]
            if better_than_benchmark:
                return (
                    sorted(better_than_benchmark, key=rank_key, reverse=True),
                    benchmark,
                    "dp_above_single_deposit_benchmark",
                )

        merged: Dict[Tuple, Tuple[float, float, List[Step]]] = {}
        for result in dp_results + ([benchmark] if benchmark is not None else []):
            key = self._result_signature(result)
            existing = merged.get(key)
            if existing is None or rank_key(result) > rank_key(existing):
                merged[key] = result

        return (
            sorted(merged.values(), key=rank_key, reverse=True),
            benchmark,
            "fallback_top_highest",
        )

    @staticmethod
    def _result_signature(result: Tuple[float, float, List[Step]]) -> Tuple:
        final_cash, _, steps = result
        open_steps = tuple(
            (
                step.month,
                step.bank_id,
                step.term,
                _r(step.amount),
            )
            for step in steps
            if step.action == ACTION_OPEN
        )
        return (_r(final_cash), open_steps)

    # Mở rộng trạng thái mỗi tháng
    # sinh nhánh state mới từ state hiện tại bằng cách thực hiện các hành động: đáo hạn, giữ cash, mở sổ mới.
    def _expand(
        self,
        month: int,
        cash: float,
        books: Tuple[Book, ...],
        months_remaining: int,
        is_last: bool,
        current_bank_id: str,
    ) -> List[Tuple[State, float, List[Step]]]:
        steps_base: List[Step] = []
        delta_base = 0.0

        # 1. Sổ đáo hạn
        # thu hoạch các sổ đáo hạn trong tháng này, cộng gốc + lãi vào cash và tính delta_interest
        live_books: List[Book] = []
        for b in books:
            if b.close_month == month:
                interest = b.interest_full()
                cash = _r(cash + b.value_at_maturity())
                delta_base += interest
                steps_base.append(Step(
                    month=month,
                    action=ACTION_MATURE,
                    amount=_r(b.value_at_maturity()),
                    term=b.term,
                    bank_id=b.bank_id,
                    bank_name=b.bank_name,
                    rate_pct=round(b.annual_rate * 100, 3),
                    note=(f"Đáo hạn: gốc {b.principal:,.0f}"
                          f" + lãi {_r(interest):,.0f} VNĐ tại {b.bank_name}")
                ))
            else:
                live_books.append(b)

        default_bank = self.bank_map.get(current_bank_id, self.banks[0])
        kkh_rate = default_bank.demand_rate

        # danh sách state mới được sinh ra
        outcomes: List[Tuple[State, float, List[Step]]] = []

        active_books = tuple(live_books)
        if is_last:
            outcomes.append(((cash, active_books), delta_base, steps_base))
            return outcomes

        # A: Giữ cash
        hold_steps = list(steps_base)
        hold_cash = cash
        hold_delta = delta_base
        kkh = _r(cash * kkh_rate / 12.0)
        if kkh > 0:
            hold_cash = _r(hold_cash + kkh)
            hold_delta += kkh
            hold_steps.append(Step(
                month=month,
                action=ACTION_KKH_INTEREST,
                amount=kkh,
                note=f"Lãi KKH {kkh_rate*100:.2f}%/năm trên {cash:,.0f} VNĐ"
            ))
        outcomes.append((
            (hold_cash, active_books),
            hold_delta,
            hold_steps + [Step(month=month, action=ACTION_HOLD_CASH, amount=_r(hold_cash),
                               note="Giữ cash sau khi cộng lãi KKH tháng này")]
        ))

        # B: Mở sổ mới (đơn / đa ngân hàng)
        if cash >= self.min_deposit and months_remaining > 0:
            plans = _generate_multi_book_plans(
                cash=cash,
                active_books=active_books,
                month=month,
                months_remaining=months_remaining,
                banks=self.banks,
                current_bank_id=current_bank_id,
                max_books=self.max_books,
                min_deposit=self.min_deposit,
                allocation_step=self.allocation_step,
                exact=self.exact,
                max_open_options=self.max_open_options,
                max_plans_per_state=self.max_plans_per_state,
                max_new_books_per_step=self.max_new_books_per_step,
            )
            # tạo outcomes
            for new_books_tuple, remaining_cash, total_fee, open_steps in plans:
                merged = active_books + new_books_tuple
                # Phí chuyển khoản được trừ vào lãi ròng
                outcomes.append((
                    (remaining_cash, merged),
                    delta_base - total_fee,
                    steps_base + open_steps,
                ))

        return outcomes

    # Tất toán cuối kỳ

    def _close_all(
        self,
        month: int,
        cash: float,
        books: Tuple[Book, ...],
        base_interest: float,
    ) -> Tuple[float, float, List[Step]]:
        steps: List[Step] = []
        total_interest = base_interest

        for b in books:
            if b.close_month <= month:
                v = b.value_at_maturity()
                interest = b.interest_full()
                cash = _r(cash + v)
                total_interest += interest
                steps.append(Step(
                    month=month, action=ACTION_MATURE, amount=_r(v),
                    term=b.term, bank_id=b.bank_id, bank_name=b.bank_name,
                    rate_pct=round(b.annual_rate * 100, 3),
                    note=f"Đáo hạn cuối kỳ: lãi {_r(interest):,.0f} VNĐ"
                ))
            else:
                months_held = month - b.open_month
                kkh = _r(b.kkh_interest(months_held))
                v = _r(b.principal + kkh)
                cash = _r(cash + v)
                total_interest += kkh
                lost = _r(b.interest_full() - kkh)
                steps.append(Step(
                    month=month, action=ACTION_EARLY_CLOSE, amount=v,
                    term=b.term, bank_id=b.bank_id, bank_name=b.bank_name,
                    rate_pct=round(b.annual_rate * 100, 3),
                    note=(f"Tất toán sớm (đáo hạn T{b.close_month})"
                          f". KKH: {kkh:,.0f} VNĐ, mất: {lost:,.0f} VNĐ lãi kỳ hạn")
                ))

        return cash, total_interest, steps

    # Beam Search

    # def _beam_prune(
    #         self,
    #         states: Dict[State, Tuple[float, List[Step]]],
    # ) -> Dict[State, Tuple[float, List[Step]]]:
    #     if len(states) <= self.top_k:
    #         return states
    #
    #     def evaluate_state(state_key: State, state_value: Tuple[float, List[Step]]) -> float:
    #         # state_key là (cash, books)
    #         # state_value là (accrued_interest, steps)
    #         cash, books = state_key
    #         accrued_interest = state_value[0]
    #
    #         # Tính "Lãi tiềm năng": Lãi đã thực thu + Lãi dự kiến của các sổ chưa đáo hạn
    #         unrealized_interest = sum(b.interest_full() for b in books)
    #
    #         return accrued_interest + unrealized_interest
    #
    #     # Sắp xếp theo Tổng lãi (Đã có + Sẽ có) thay vì chỉ lãi đã thu
    #     sorted_s = sorted(
    #         states.items(),
    #         key=lambda x: evaluate_state(x[0], x[1]),
    #         reverse=True
    #     )
    #
    #     return dict(sorted_s[:self.top_k])

    # def _beam_prune(
    #         self,
    #         states: Dict[State, Tuple[float, List[Step]]],
    #         months_remaining: int  # Truyền thêm tham số này vào
    # ) -> Dict[State, Tuple[float, List[Step]]]:
    #     if len(states) <= self.top_k:
    #         return states
    #
    #     def evaluate_state(state_key: State, state_value: Tuple[float, List[Step]]) -> float:
    #         cash, books = state_key
    #         accrued_interest = state_value[0]
    #
    #         # 1. Lãi đã thực thu (đã vào túi)
    #         current_profit = accrued_interest
    #
    #         # 2. Lãi chắc chắn sẽ có từ các sổ đang mở
    #         unrealized_interest = sum(b.interest_full() for b in books)
    #
    #         # 3. HEURISTIC: Lãi dự kiến từ số tiền mặt (cash) hiện tại
    #         # Giả sử cash này ít nhất cũng gửi được lãi KKH hoặc lãi 1 tháng từ nay đến cuối kỳ
    #         # Điều này giúp "bảo vệ" các phương án đang giữ nhiều cash để chờ nhảy ngân hàng
    #         min_future_rate = 0.04  # Giả định lãi suất tối thiểu có thể tìm được là 4%/năm
    #         estimated_future_cash_interest = cash * (min_future_rate * months_remaining / 12.0)
    #
    #         return current_profit + unrealized_interest + estimated_future_cash_interest
    #
    #     # Sắp xếp theo "Tổng lãi kỳ vọng khi kết thúc dự án"
    #     sorted_s = sorted(
    #         states.items(),
    #         key=lambda x: evaluate_state(x[0], x[1]),
    #         reverse=True
    #     )
    #
    #     return dict(sorted_s[:self.top_k])

    def _beam_prune(
            self,
            states: Dict[State, Tuple[float, List[Step]]],
            months_remaining: int
    ) -> Dict[State, Tuple[float, List[Step]]]:
        if len(states) <= self.top_k:
            return states

        # Lấy lãi KKH cao nhất thị trường để tính cho phần tiền mặt còn thừa
        max_demand_rate = max(b.demand_rate for b in self.banks)

        # hàm chấm điểm trạng thái để sắp xếp và chọn ra top_k trạng thái tốt nhất. Điểm số được tính dựa trên tổng giá trị dự kiến tại thời điểm kết thúc dự án (T) và giá trị đang có
        def evaluate_state(state_key: State, state_value: Tuple[float, List[Step]]) -> float:
            cash, books = state_key
            accrued_interest = state_value[0]

            # 1. Tiền mặt hiện có + Lãi đã bỏ túi
            current_net_worth = cash + accrued_interest

            # 2. Cộng TOÀN BỘ lãi sẽ nhận được từ các sổ đang mở khi chúng đáo hạn
            # Đây là điểm mấu chốt để bảo vệ sổ 12T
            total_future_interest = sum(b.interest_full() for b in books)

            book_principal = sum(b.principal for b in books)

            # 3. Tiền mặt (cash) hiện tại sẽ sinh lãi KKH cho đến hết kỳ hạn mục tiêu
            future_cash_growth = cash * (max_demand_rate * months_remaining / 12.0)

            # Tổng giá trị dự kiến tại thời điểm kết thúc dự án (T)
            return current_net_worth + total_future_interest + future_cash_growth + book_principal

        # Sắp xếp và giữ lại những trạng thái có "Giá trị cuối kỳ" cao nhất
        sorted_s = sorted(
            states.items(),
            key=lambda x: evaluate_state(x[0], x[1]),
            reverse=True
        )
        return dict(sorted_s[:self.top_k])
    # Tiện ích

    def _infer_current_bank(self, books: Tuple[Book, ...]) -> str:
        """Xác định ngân hàng hiện tại từ sổ gần nhất đang mở."""
        if not books:
            return self.default_bank_id
        latest = max(books, key=lambda b: b.open_month)
        return latest.bank_id

    def _format_result(
        self,
        rank: int,
        final_cash: float,
        interest_earned: float,
        steps: List[Step],
        initial_amount: float,
    ) -> Dict:
        # Phân tích ngân hàng được dùng
        banks_used = list({s.bank_id for s in steps
                          if s.action == ACTION_OPEN and s.bank_id})
        banks_used_names = [self.bank_map[bid].name for bid in banks_used
                           if bid in self.bank_map]
        total_fees = sum(s.amount for s in steps if s.action == ACTION_TRANSFER_FEE)

        return {
            "rank": rank,
            "final_amount": _r(final_cash),
            "interest_earned": _r(interest_earned),
            "interest_rate_effective_pct": _r(interest_earned / initial_amount * 100)
                                           if initial_amount > 0 else 0.0,
            "banks_used": banks_used_names,
            "total_transfer_fees": _r(total_fees),
            "summary": {
                "initial_amount": initial_amount,
                "net_contribution": _r(initial_amount),
            },
            "steps": [self._step_to_dict(s) for s in steps],
        }

    @staticmethod
    def _step_to_dict(s: Step) -> Dict:
        d: Dict = {"month": s.month, "action": s.action, "amount": s.amount}
        if s.term is not None:      d["term_months"] = s.term
        if s.bank_id is not None:   d["bank_id"] = s.bank_id
        if s.bank_name is not None: d["bank_name"] = s.bank_name
        if s.rate_pct is not None:  d["annual_rate_pct"] = s.rate_pct
        if s.fee is not None:       d["fee"] = s.fee
        if s.note:                  d["note"] = s.note
        return d
