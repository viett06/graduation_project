import os
import json
import re
import httpx
from groq import Groq
from dotenv import load_dotenv
from app.models.bank import Bank
from app.schemas.bankSchema import CompareCalculateRequest, InterestCalculateRequest
from app.schemas.savingPlanSchema import SavingPlanCreate
from app.service.bankService import BankService
from app.service.chatbotConversationService import ChatbotConversationService
from app.service.SavingPlanService import SavingPlanService
from sqlalchemy.orm import Session
from datetime import date
from decimal import Decimal

load_dotenv()

http_client = httpx.Client(proxy=None)

client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    http_client=http_client
)

OUT_OF_SCOPE_ANSWER = "câu hỏi của bạn sẽ được cập nhật sau."
MAX_RATE_ROWS_FOR_LLM = 15
MODEL_NAME = "llama-3.3-70b-versatile"
ANSWER_MAX_TOKENS = 500
ROUTER_SYSTEM_PROMPT = """
Bạn là bộ phân tích ý định cho chatbot tài chính ngân hàng.
Chỉ trả về JSON hợp lệ, không markdown, không giải thích.

Schema:
{
  "intent": "get_rates | calculate_deposit_interest | compare_bank_interest | create_saving_plan | out_of_scope",
  "params": {}
}

Quy tắc:
- Luôn dùng Context hội thoại gần đây nếu Prompt hiện tại là câu trả lời tiếp nối.
- Nếu Prompt hiện tại chỉ bổ sung dữ liệu còn thiếu như số tiền, kỳ hạn, ngày gửi,
  hãy giữ intent và ngân hàng từ context trước đó rồi merge params.
- get_rates: khi hỏi lãi suất, so sánh lãi suất, lãi suất cao nhất.
  params gồm: name, type, code, codes, term_month, sort, limit.
  sort là "highest", "compare" hoặc "list".
  codes là danh sách mã ngân hàng nếu người dùng nêu nhiều mã, ví dụ ["PVB","SGB"].
- calculate_deposit_interest: khi hỏi gửi X tiền Y tháng được bao nhiêu lãi.
  params gồm: bank_id, bank_code, bank_name, channel, term_month, amount, deposit_date.
- compare_bank_interest: khi hỏi so sánh tiền lãi/tổng tiền sinh ra giữa 2 ngân hàng.
  params gồm: codes, bank_names, channel, term_month, amount, deposit_date.
  Nếu người dùng cũng hỏi so sánh lãi suất, vẫn dùng intent này và giữ codes/term_month.
- create_saving_plan: khi hỏi lập/tối ưu kế hoạch tiết kiệm.
  params gồm đúng dữ liệu cần cho kế hoạch tiết kiệm nếu có.
- out_of_scope: câu hỏi ngoài ngân hàng/lãi suất/tiết kiệm.
- Nếu thiếu amount cho compare_bank_interest hoặc calculate_deposit_interest thì để amount là null.
- Giá trị không có thì dùng null, list không có thì dùng [].
"""


def json_default(value):
    if isinstance(value, (date, Decimal)):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)


def to_jsonable(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=json_default))


def compact_rate_rows(rows: list[dict], limit: int = MAX_RATE_ROWS_FOR_LLM) -> list[dict]:
    def rate_value(item: dict) -> float:
        try:
            return float(item.get("rate") or 0)
        except (TypeError, ValueError):
            return 0

    sorted_rows = sorted(rows or [], key=rate_value, reverse=True)
    compacted = []
    seen = set()

    for item in sorted_rows:
        key = (
            item.get("code"),
            item.get("term_month"),
            item.get("rate"),
        )
        if key in seen:
            continue
        seen.add(key)
        compacted.append({
            "code": item.get("code"),
            "type": item.get("type"),
            "term_month": item.get("term_month"),
            "rate": item.get("rate"),
        })
        if len(compacted) >= limit:
            break

    return compacted


def parse_json_object(content: str) -> dict:
    if not content:
        return {"intent": "out_of_scope", "params": {}}

    cleaned = content.strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"intent": "out_of_scope", "params": {}}

    if not isinstance(parsed, dict):
        return {"intent": "out_of_scope", "params": {}}

    parsed.setdefault("intent", "out_of_scope")
    parsed.setdefault("params", {})
    return parsed


def normalize_router_params(params: dict) -> dict:
    normalized = dict(params or {})

    for key in ("name", "type", "code", "bank_code", "bank_name", "channel", "deposit_date"):
        if normalized.get(key) == "":
            normalized[key] = None

    if normalized.get("code"):
        normalized["code"] = normalized["code"].strip().upper()
    if normalized.get("bank_code"):
        normalized["bank_code"] = normalized["bank_code"].strip().upper()

    codes = normalized.get("codes") or []
    if normalized.get("code") and normalized["code"] not in codes:
        codes.append(normalized["code"])
    normalized["codes"] = [code.strip().upper() for code in codes if code]

    bank_names = normalized.get("bank_names") or []
    normalized["bank_names"] = [name.strip() for name in bank_names if name]

    if normalized.get("limit") is None:
        normalized["limit"] = MAX_RATE_ROWS_FOR_LLM
    else:
        normalized["limit"] = int(normalized["limit"])

    for key in ("term_month", "duration_month", "bank_id", "user_id"):
        if normalized.get(key) is not None:
            normalized[key] = int(normalized[key])

    for key in ("amount", "total_amount", "goal_amount", "monthly_extra"):
        if normalized.get(key) is not None:
            normalized[key] = float(normalized[key])

    return normalized


def extract_bank_codes_from_message(user_message: str) -> list[str]:
    ignored_words = {
        "LAI", "SUAT", "NGAN", "HANG", "CAO", "NHAT", "BAO", "NHIEU",
        "HIEN", "NAY", "CUA", "KY", "HAN", "THANG", "SO", "SANH",
        "NEU", "GUI", "TIEN", "LA", "DUOC", "SINH", "RA", "GIUA",
    }
    codes = []
    for token in re.findall(r"\b[A-Za-z]{2,10}\b", user_message):
        code = token.upper()
        if code in ignored_words:
            continue
        if code not in codes:
            codes.append(code)
    return codes


def extract_term_month_from_message(user_message: str) -> int | None:
    match = re.search(r"(\d{1,2})\s*(?:tháng|thang)", user_message.lower())
    return int(match.group(1)) if match else None


def infer_rate_route_from_message(user_message: str) -> dict | None:
    lowered = user_message.lower()
    if "lãi suất" not in lowered and "lai suat" not in lowered:
        return None

    codes = extract_bank_codes_from_message(user_message)
    sort = "list"
    if any(keyword in lowered for keyword in ["cao nhất", "cao nhat", "tốt nhất", "tot nhat", "max"]):
        sort = "highest"
    elif any(keyword in lowered for keyword in ["so sánh", "so sanh"]):
        sort = "compare"

    params = normalize_router_params({
        "codes": codes,
        "term_month": extract_term_month_from_message(user_message),
        "sort": sort,
        "limit": 5 if sort == "highest" else MAX_RATE_ROWS_FOR_LLM,
    })

    return {
        "intent": "get_rates",
        "params": params,
    }


def ensure_supported_route(user_message: str, route: dict) -> dict:
    if route.get("intent") != "out_of_scope":
        return route

    inferred_route = infer_rate_route_from_message(user_message)
    return inferred_route or route


def truncate_text(value: str, max_chars: int = 12000) -> str:
    return value if len(value) <= max_chars else value[:max_chars]


def format_history_for_router(history_messages: list[dict[str, str]]) -> str:
    if not history_messages:
        return ""

    lines = []
    for message in history_messages[-8:]:
        lines.append(f"{message['role']}: {message['content']}")
    return "\n".join(lines)


def classify_message(user_message: str, history_messages: list[dict[str, str]] | None = None) -> dict:
    history_text = format_history_for_router(history_messages or [])
    user_content = (
        f"Context hội thoại gần đây:\n{history_text}\n\n"
        f"Prompt hiện tại: {user_message}"
        if history_text
        else user_message
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
        max_tokens=600,
    )
    route = parse_json_object(response.choices[0].message.content)
    route["params"] = normalize_router_params(route.get("params") or {})
    route = ensure_supported_route(user_message, route)
    return route


def filter_rows_by_term(rows: list[dict], term_month: int | None) -> list[dict]:
    if term_month is None:
        return rows
    return [row for row in rows if row.get("term_month") == term_month]


def format_rate_answer(params: dict, rows: list[dict]) -> str:
    limit = min(int(params.get("limit") or MAX_RATE_ROWS_FOR_LLM), MAX_RATE_ROWS_FOR_LLM)
    compacted = compact_rate_rows(rows, limit=limit)

    if not compacted:
        term_text = f" kỳ hạn {params.get('term_month')} tháng" if params.get("term_month") else ""
        return f"Hiện tại tôi chưa tìm thấy dữ liệu lãi suất{term_text} phù hợp."

    best = compacted[0]
    term_text = f" kỳ hạn {params.get('term_month')} tháng" if params.get("term_month") else ""
    sort = params.get("sort")
    codes = params.get("codes") or []

    if sort == "highest":
        lines = [
            (
                f"Lãi suất cao nhất hiện tại là {best['rate']}%/năm tại ngân hàng "
                f"{best['code']}, kỳ hạn {best['term_month']} tháng."
            )
        ]
        if len(compacted) > 1:
            lines.append("Một vài mức cao tiếp theo:")
            for item in compacted[1:5]:
                lines.append(f"- {item['code']}: {item['rate']}%/năm, kỳ hạn {item['term_month']} tháng")
        return "\n".join(lines)

    if sort == "compare" or len(codes) > 1:
        lines = [f"So sánh lãi suất{term_text}:"]
    else:
        lines = [f"Lãi suất{term_text}:"]

    for item in compacted:
        lines.append(f"- {item['code']}: {item['rate']}%/năm, kỳ hạn {item['term_month']} tháng")

    if sort == "compare" or len(codes) > 1:
        lines.append(f"Kết luận: {best['code']} đang có lãi suất cao nhất trong nhóm trên.")

    return "\n".join(lines)


def format_calculate_interest_answer(result: dict) -> str:
    if result.get("error"):
        return result["error"]

    return (
        f"Ngân hàng {result['bank_name']} áp dụng lãi suất {result['interest_rate']}%/năm "
        f"cho kỳ hạn {result['term_month']} tháng qua kênh {result['channel']}. "
        f"Tiền lãi dự kiến là {result['interest_amount']:,.0f} VND, "
        f"tổng nhận cuối kỳ là {result['total_amount']:,.0f} VND. "
        f"Ngày đáo hạn: {result['maturity_date']}."
    )


def format_saving_plan_answer(result: dict) -> str:
    if result.get("error"):
        return result["error"]

    goal_text = "đạt mục tiêu" if result.get("is_goal_met") else "chưa đạt mục tiêu"
    return (
        f"Kế hoạch #{result.get('plan_id')} dùng thuật toán {result.get('algorithm_used')}. "
        f"Số tiền cuối kỳ dự kiến: {result.get('final_amount', 0):,.0f} VND, "
        f"lãi đạt được: {result.get('achieved_interest', 0):,.0f} VND, {goal_text}."
    )


def generate_natural_answer(
        user_message: str,
        route: dict,
        result_context: dict,
        history_messages: list[dict[str, str]] | None = None,
) -> str:
    if route.get("intent") == "out_of_scope":
        return OUT_OF_SCOPE_ANSWER

    compact_context = truncate_text(
        json.dumps(result_context, ensure_ascii=False, default=json_default),
        max_chars=12000,
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "Bạn là trợ lý tài chính ngân hàng. Viết câu trả lời tự nhiên bằng tiếng Việt "
                    "dựa duy nhất trên JSON context. Không bịa số liệu. Nếu context có missing_fields, "
                    "hãy hỏi người dùng bổ sung đúng trường còn thiếu. Trả lời ngắn gọn."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Prompt gốc: {user_message}\n"
                    f"Context hội thoại: {format_history_for_router(history_messages or [])}\n"
                    f"Route: {json.dumps(route, ensure_ascii=False, default=json_default)}\n"
                    f"Context: {compact_context}"
                ),
            },
        ],
        temperature=0.2,
        max_tokens=ANSWER_MAX_TOKENS,
    )

    return response.choices[0].message.content or OUT_OF_SCOPE_ANSWER


def fallback_context_answer(result_context: dict) -> str:
    if result_context.get("fallback_answer"):
        return result_context["fallback_answer"]

    if result_context.get("type") == "compare_bank_interest":
        comparison = result_context.get("comparison") or {}
        if comparison.get("missing_fields"):
            missing = ", ".join(comparison["missing_fields"])
            return f"Bạn cần bổ sung {missing} để tôi tính và so sánh số tiền lãi giữa hai ngân hàng."
        if comparison.get("error"):
            return comparison["error"]

    if result_context.get("message"):
        return result_context["message"]

    return OUT_OF_SCOPE_ANSWER


async def safe_get_rates(bank_service: BankService, args: dict):

    code = args.get("code")
    name = args.get("name")
    bank_type = args.get("type")

    norm = {
        "code": code.strip().upper() if code else None,
        "name": f"%{name.strip()}%" if name else None,
        "type": f"%{bank_type.strip().upper()}%" if bank_type else None
    }

    result = await bank_service.get_all_banks_and_rates_for_chat_bot(**norm)

    if not result and norm["name"]:
        fallback_args = {**norm, "code": None}
        result = await bank_service.get_all_banks_and_rates_for_chat_bot(**fallback_args)

    return result


def resolve_bank_id(session: Session, bank_id: int | None, bank_code: str | None, bank_name: str | None) -> int | None:
    if bank_id:
        return bank_id

    query = session.query(Bank).filter(Bank.status == True)

    if bank_code:
        bank = query.filter(Bank.code.ilike(bank_code.strip())).first()
        if bank:
            return bank.id

    if bank_name:
        bank = query.filter(Bank.name.ilike(f"%{bank_name.strip()}%")).first()
        if bank:
            return bank.id

    return None


def calculate_deposit_interest(session: Session, bank_service: BankService, args: dict):
    resolved_bank_id = resolve_bank_id(
        session=session,
        bank_id=args.get("bank_id"),
        bank_code=args.get("bank_code"),
        bank_name=args.get("bank_name"),
    )

    if not resolved_bank_id:
        return {
            "error": "Không tìm thấy ngân hàng phù hợp. Vui lòng cung cấp bank_id hoặc mã ngân hàng chính xác."
        }

    deposit_date_arg = args.get("deposit_date")
    deposit_date = date.fromisoformat(deposit_date_arg) if deposit_date_arg else date.today()

    request = InterestCalculateRequest(
        bank_id=resolved_bank_id,
        channel=(args.get("channel") or "ONLINE").upper(),
        term_month=args["term_month"],
        amount=args["amount"],
        deposit_date=deposit_date,
    )

    return bank_service.calculate_interest(request).model_dump()


def compare_bank_interest(session: Session, bank_service: BankService, args: dict) -> dict:
    codes = args.get("codes") or []
    bank_names = args.get("bank_names") or []
    term_month = args.get("term_month")
    amount = args.get("amount")
    channel = (args.get("channel") or "ONLINE").upper()
    deposit_date_arg = args.get("deposit_date")
    deposit_date = date.fromisoformat(deposit_date_arg) if deposit_date_arg else date.today()

    if len(codes) + len(bank_names) < 2:
        return {
            "error": "Cần ít nhất 2 ngân hàng để so sánh tiền lãi."
        }

    missing_fields = []
    if term_month is None:
        missing_fields.append("term_month")
    if amount is None:
        missing_fields.append("amount")

    if missing_fields:
        return {
            "missing_fields": missing_fields,
            "message": "Cần bổ sung kỳ hạn và số tiền gửi để tính tiền lãi giữa hai ngân hàng.",
        }

    first_bank = {
        "code": codes[0] if len(codes) > 0 else None,
        "name": bank_names[0] if len(bank_names) > 0 else None,
    }
    second_bank = {
        "code": codes[1] if len(codes) > 1 else None,
        "name": bank_names[1] if len(bank_names) > 1 else None,
    }

    first_bank_id = resolve_bank_id(session, None, first_bank["code"], first_bank["name"])
    second_bank_id = resolve_bank_id(session, None, second_bank["code"], second_bank["name"])

    if not first_bank_id or not second_bank_id:
        return {
            "error": "Không tìm thấy đủ thông tin ngân hàng để so sánh.",
            "banks": [first_bank, second_bank],
        }

    first_request = InterestCalculateRequest(
        bank_id=first_bank_id,
        channel=channel,
        term_month=term_month,
        amount=amount,
        deposit_date=deposit_date,
    )
    try:
        first_result = bank_service.calculate_interest(first_request).model_dump()
    except Exception as e:
        return {
            "error": f"Không tính được tiền lãi cho ngân hàng thứ nhất: {e}",
            "banks": [first_bank, second_bank],
        }

    second_request = CompareCalculateRequest(
        bank_id=second_bank_id,
        channel=channel,
        term_month=term_month,
        amount=amount,
        deposit_date=deposit_date,
        previous_result=first_result["total_amount"],
    )
    try:
        second_result = bank_service.compare_calculate_interest(second_request).model_dump()
    except Exception as e:
        return {
            "error": f"Không tính được tiền lãi cho ngân hàng thứ hai: {e}",
            "banks": [first_bank, second_bank],
            "first_bank_result": first_result,
        }

    return {
        "amount": amount,
        "term_month": term_month,
        "channel": channel,
        "deposit_date": deposit_date,
        "first_bank": first_result,
        "second_bank": second_result,
        "better_bank": (
            first_result["bank_name"]
            if first_result["total_amount"] >= second_result["total_amount"]
            else second_result["bank_name"]
        ),
        "difference_total_amount": abs(second_result["compare_result"]),
        "difference_interest_amount": abs(
            second_result["interest_amount"] - first_result["interest_amount"]
        ),
    }


def create_saving_plan(saving_plan_service: SavingPlanService, args: dict):
    duration_month = args["duration_month"]
    total_amount = args["total_amount"]
    goal_amount = args.get("goal_amount") or total_amount

    request = SavingPlanCreate(
        name=args.get("name") or "Kế hoạch tiết kiệm từ chatbot",
        duration_month=duration_month,
        total_amount=total_amount,
        goal_amount=goal_amount,
        monthly_extra=args.get("monthly_extra") or 0,
        extra_schedule=args.get("extra_schedule") or [],
        withdrawal_schedule=args.get("withdrawal_schedule") or [],
        prefer_rate=(args.get("prefer_rate") or "ONLINE").upper(),
        risk_tolerance=(args.get("risk_tolerance") or "low").lower(),
        algorithm_used=(args.get("algorithm_used") or "dp").lower(),
        codes=[code.strip().upper() for code in (args.get("codes") or []) if code],
        notes=args.get("notes"),
    )

    return saving_plan_service.create_plan(args.get("user_id") or 6, request)


async def execute_function_call(
    intent: str,
    params: dict,
    session: Session,
    bank_service: BankService,
    saving_plan_service: SavingPlanService,
) -> dict:
    if intent == "get_rates":
        codes = params.get("codes") or []
        names = params.get("bank_names") or []
        if params.get("name"):
            names.append(params["name"])
        if params.get("code") and params["code"] not in codes:
            codes.append(params["code"])

        rows = bank_service.get_rates_for_chatbot(
            codes=codes,
            names=names,
            term_month=params.get("term_month"),
            channel=params.get("channel"),
            amount=params.get("amount"),
            limit=min(params.get("limit") or MAX_RATE_ROWS_FOR_LLM, MAX_RATE_ROWS_FOR_LLM),
        )
        return {
            "type": "rate_lookup",
            "params": params,
            "rates": rows,
            "fallback_answer": format_rate_answer(params, rows),
        }

    if intent == "calculate_deposit_interest":
        if params.get("amount") is None:
            return {
                "type": "calculate_deposit_interest",
                "missing_fields": ["amount"],
                "message": "Cần số tiền gửi để tính tiền lãi.",
            }
        try:
            result = calculate_deposit_interest(session, bank_service, params)
        except Exception as e:
            result = {"error": str(e)}
        return {
            "type": "calculate_deposit_interest",
            "params": params,
            "calculation": result,
            "fallback_answer": format_calculate_interest_answer(result),
        }

    if intent == "compare_bank_interest":
        deposit_date_arg = params.get("deposit_date")
        deposit_date_value = date.fromisoformat(deposit_date_arg) if deposit_date_arg else None
        result = bank_service.compare_interest_for_chatbot(
            codes=params.get("codes") or [],
            names=params.get("bank_names") or [],
            term_month=params.get("term_month"),
            amount=params.get("amount"),
            channel=(params.get("channel") or "ONLINE").upper(),
            deposit_date=deposit_date_value,
        )
        return {
            "type": "compare_bank_interest",
            "params": params,
            "comparison": result,
        }

    if intent == "create_saving_plan":
        result = create_saving_plan(saving_plan_service, params)
        return {
            "type": "create_saving_plan",
            "params": params,
            "plan": result,
            "fallback_answer": format_saving_plan_answer(result),
        }

    return {
        "type": "out_of_scope",
        "message": OUT_OF_SCOPE_ANSWER,
    }


async def run_agent(
        user_message: str,
        session,
        user_id: int | None = None,
        use_context: bool = True,
) -> dict:

    bank_service = BankService(session)
    saving_plan_service = SavingPlanService(session)
    conversation_service = ChatbotConversationService(session)

    print(f"\n{'='*60}")
    print(f"user: {user_message}")
    print(f"\n{'='*60}")

    conversation = None
    history_messages = []

    try:
        if use_context:
            conversation = conversation_service.get_or_create_user_conversation(
                user_id=user_id,
                title=user_message[:80],
            )
            history_messages = conversation_service.build_context_messages(conversation.id, limit=20)
            conversation_service.add_user_message(conversation.id, user_message)

        route = classify_message(user_message, history_messages)
        print(f"\n[Router] {route}")
        result_context = await execute_function_call(
            route.get("intent", "out_of_scope"),
            route.get("params") or {},
            session,
            bank_service,
            saving_plan_service,
        )
        print(f"\n[Function Result] {json.dumps(result_context, ensure_ascii=False, default=json_default)}")
        try:
            answer = generate_natural_answer(user_message, route, result_context, history_messages)
        except Exception as e:
            print(f"[Answer Generation Error] {e}")
            answer = fallback_context_answer(result_context)

        if use_context and conversation:
            conversation_service.add_assistant_message(
                conversation.id,
                answer,
                intent=route.get("intent"),
                message_metadata=to_jsonable({
                    "route": route,
                    "result_context": result_context,
                }),
            )
            conversation_service.commit()
    except Exception as e:
        print(f"[Agent Error] {e}")
        conversation_service.rollback()
        conversation = None
        answer = OUT_OF_SCOPE_ANSWER

    print(f"\n[Assistant]: {answer}")
    return {
        "conversation_id": conversation.id if conversation else None,
        "answer": answer,
    }
