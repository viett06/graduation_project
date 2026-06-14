import os
import json
import re
import httpx
import asyncio
from groq import Groq
from dotenv import load_dotenv
from app.agent.chatbot_tools import tools
from app.models.bank import Bank
from app.schemas.bankSchema import InterestCalculateRequest
from app.schemas.savingPlanSchema import SavingPlanCreate
from app.service.bankService import BankService
from app.service.chatbotConversationService import ChatbotConversationService
from app.service.SavingPlanService import SavingPlanService
from sqlalchemy.orm import Session
from datetime import date
from decimal import Decimal
from collections.abc import AsyncGenerator

load_dotenv()


# =============================================================================
# 1. Runtime Configuration
# =============================================================================

http_client = httpx.Client(proxy=None)

client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    http_client=http_client
)

OUT_OF_SCOPE_ANSWER = "câu hỏi của bạn sẽ được cập nhật sau."
MAX_RATE_ROWS_FOR_LLM = 15
MODEL_NAME = "llama-3.3-70b-versatile"
ANSWER_MAX_TOKENS = 500
MAX_TOOL_ROUNDS = 3
MAX_MODEL_RETRIES = 2
STREAM_CHUNK_SIZE = 24
TOOL_RETRY_SYSTEM_PROMPT = """
Tool call trước đó bị sai format hoặc sai schema.
Hãy gọi tool bằng API tool_calls hợp lệ của hệ thống, không viết tool call trong text.
Chỉ dùng đúng tên tool và đúng properties đã khai báo. Nếu thiếu dữ liệu, vẫn gọi tool với những field đã biết.
"""
ANSWER_RETRY_SYSTEM_PROMPT = """
Lần trả lời trước không hợp lệ. Hãy trả lời ngắn gọn bằng tiếng Việt, không gọi tool trong text,
không tự viết JSON, và không bịa số liệu.
"""
AGENT_SYSTEM_PROMPT = f"""
Bạn là trợ lý tài chính ngân hàng bằng tiếng Việt.

Nguyên tắc:
- Khi người dùng hỏi về lãi suất, tính lãi, so sánh ngân hàng hoặc lập kế hoạch tiết kiệm,
  hãy dùng tools được cung cấp để lấy dữ liệu backend. Không tự đoán số liệu.
- Nếu người dùng trả lời tiếp để bổ sung dữ liệu còn thiếu, hãy dựa vào Context hội thoại gần đây
  và gọi lại tool phù hợp với dữ liệu đã merge.
- Nếu thiếu trường bắt buộc để tính toán, vẫn gọi tool khi có thể; backend sẽ trả missing_fields,
  sau đó hỏi lại đúng thông tin còn thiếu.
- Nếu câu hỏi ngoài phạm vi ngân hàng/lãi suất/tiết kiệm, trả lời đúng câu: "{OUT_OF_SCOPE_ANSWER}"
- Trả lời ngắn gọn, tự nhiên, không bịa dữ liệu ngoài tool result.
- Khi cần dùng tool, hãy gọi tool qua cơ chế tool calling được cung cấp.
Không tự viết cú pháp <function=...> trong nội dung trả lời.
Không trả JSON tool call trong text.
"""

TOOL_NAMES = {tool["function"]["name"] for tool in tools}


# =============================================================================
# 2. Serialization And Stream Helpers
# =============================================================================

def json_default(value):
    if isinstance(value, (date, Decimal)):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)


def to_jsonable(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=json_default))


def encode_stream_event(event: str, data: dict) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False, default=json_default)}\n\n"
    )


def split_text_chunks(text: str, chunk_size: int = STREAM_CHUNK_SIZE) -> list[str]:
    if not text:
        return []
    return [text[index:index + chunk_size] for index in range(0, len(text), chunk_size)]


# =============================================================================
# 3. Input Normalization
# =============================================================================

def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def split_code_values(values) -> list[str]:
    codes = []
    for value in as_list(values):
        for code in re.split(r"[,;/]|\s+(?:và|va|and)\s+", str(value), flags=re.IGNORECASE):
            code = code.strip()
            if code:
                codes.append(code)
    return codes


def coerce_int(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    match = re.search(r"\d+(?:[.,]\d+)?", str(value))
    return int(float(match.group(0).replace(",", "."))) if match else None


def coerce_float(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().lower()
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    if not match:
        return None

    number = float(match.group(0).replace(",", "."))
    if any(unit in text for unit in ("tỷ", "ty", "billion")):
        return number * 1_000_000_000
    if any(unit in text for unit in ("triệu", "trieu", "million")) or re.search(r"\d\s*tr\b", text):
        return number * 1_000_000
    if any(unit in text for unit in ("nghìn", "ngan", "k ")):
        return number * 1_000
    return number


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# =============================================================================
# 4. Model Client And Provider Error Recovery
# =============================================================================

def parse_failed_tool_generation(error: Exception) -> tuple[str, dict] | None:
    raw_error = str(error)
    patterns = [
        r"<function=(?P<name>[A-Za-z_][A-Za-z0-9_]*)>?\s*(?P<args>\{.*?\})\s*>?</function>",
        r"attempted to call tool ['\"](?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<args>\{.*?\})['\"]",
    ]

    match = None
    for pattern in patterns:
        match = re.search(pattern, raw_error, flags=re.DOTALL)
        if match:
            break

    if not match:
        for tool_name in TOOL_NAMES:
            fallback_match = re.search(
                rf"{re.escape(tool_name)}\s*(?P<args>\{{.*?\}})",
                raw_error,
                flags=re.DOTALL,
            )
            if fallback_match:
                match = fallback_match
                name = tool_name
                break
        else:
            return None
    else:
        name = match.group("name")

    try:
        arguments = json.loads(match.group("args"))
    except json.JSONDecodeError:
        return None

    return name, arguments


def is_model_tool_error(error: Exception) -> bool:
    raw_error = str(error)
    return (
        "tool_use_failed" in raw_error
        or "Failed to call a function" in raw_error
        or "failed_generation" in raw_error
        or "tool call validation failed" in raw_error
    )


def create_chat_completion_with_retry(
        messages: list[dict],
        use_tools: bool = False,
        retry_system_prompt: str = ANSWER_RETRY_SYSTEM_PROMPT,
        initial_temperature: float = 0.2,
):
    last_error = None

    for attempt in range(MAX_MODEL_RETRIES + 1):
        attempt_messages = messages
        if attempt > 0:
            attempt_messages = [
                *messages,
                {"role": "system", "content": retry_system_prompt},
            ]

        try:
            kwargs = {
                "model": MODEL_NAME,
                "messages": attempt_messages,
                "temperature": 0 if attempt > 0 else initial_temperature,
                "max_tokens": ANSWER_MAX_TOKENS,
            }
            if use_tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            last_error = e
            if use_tools and parse_failed_tool_generation(e):
                raise
            if not use_tools or not is_model_tool_error(e) or attempt >= MAX_MODEL_RETRIES:
                raise
            print(f"[Model Retry {attempt + 1}/{MAX_MODEL_RETRIES}] {e}")

    raise last_error


def create_chat_completion_stream(
        messages: list[dict],
        initial_temperature: float = 0.2,
):
    return client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=initial_temperature,
        max_tokens=ANSWER_MAX_TOKENS,
        stream=True,
    )


def iter_stream_content_chunks(stream):
    for event in stream:
        if not event.choices:
            continue
        delta = event.choices[0].delta
        content = getattr(delta, "content", None)
        if content:
            yield content


# =============================================================================
# 5. Tool Argument Normalization And Supplemental Context
# =============================================================================

def compact_rate_rows(
        rows: list[dict],
        limit: int = MAX_RATE_ROWS_FOR_LLM,
        unique_bank: bool = False,
) -> list[dict]:
    def rate_value(item: dict) -> float:
        try:
            return float(item.get("rate") or 0)
        except (TypeError, ValueError):
            return 0

    sorted_rows = sorted(rows or [], key=rate_value, reverse=True)
    compacted = []
    seen = set()

    for item in sorted_rows:
        key = item.get("code") if unique_bank else (
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


def normalize_tool_params(params: dict) -> dict:
    normalized = dict(params or {})

    if normalized.get("bank_name") and not normalized.get("name"):
        normalized["name"] = normalized["bank_name"]
    if normalized.get("bank_code") and not normalized.get("code"):
        normalized["code"] = normalized["bank_code"]
    if normalized.get("bank_type") and not normalized.get("type"):
        normalized["type"] = normalized["bank_type"]

    for key in ("name", "type", "code", "bank_code", "bank_name", "bank_type", "channel", "deposit_date"):
        if normalized.get(key) == "":
            normalized[key] = None

    if normalized.get("code"):
        normalized["code"] = normalized["code"].strip().upper()
    if normalized.get("bank_code"):
        normalized["bank_code"] = normalized["bank_code"].strip().upper()

    codes = split_code_values(normalized.get("codes")) + split_code_values(normalized.get("bank_codes"))
    if normalized.get("code") and normalized["code"] not in codes:
        codes.append(normalized["code"])
    normalized["codes"] = [code.strip().upper() for code in codes if code]

    bank_names = as_list(normalized.get("bank_names"))
    if normalized.get("name"):
        bank_names.append(normalized["name"])
    normalized["bank_names"] = [name.strip() for name in bank_names if name]

    normalized["limit"] = coerce_int(normalized.get("limit")) or MAX_RATE_ROWS_FOR_LLM

    for key in ("term_month", "duration_month", "bank_id", "user_id"):
        normalized[key] = coerce_int(normalized.get(key))

    for key in ("amount", "total_amount", "goal_amount"):
        normalized[key] = coerce_float(normalized.get(key))

    return normalized


def sanitize_tool_arguments(arguments) -> dict:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return {}
    if not isinstance(arguments, dict):
        return {}
    if isinstance(arguments.get("arguments"), dict) and len(arguments) == 1:
        return arguments["arguments"]
    return arguments


def extract_amount_phrase(text: str) -> str | None:
    match = re.search(
        r"\d+(?:[.,]\d+)?\s*(?:tỷ|ty|billion|triệu|trieu|tr|million|nghìn|ngan|k|vnd|đ|dong|đồng)",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(0) if match else None


def extract_month_value(text: str) -> int | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:tháng|thang|month)", text, flags=re.IGNORECASE)
    if match:
        return coerce_int(match.group(1))

    year_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:năm|nam|year)", text, flags=re.IGNORECASE)
    if year_match:
        years = coerce_int(year_match.group(1))
        return years * 12 if years is not None else None

    return None


def extract_channel_value(text: str) -> str | None:
    lowered = text.lower()
    if "online" in lowered or "trực tuyến" in lowered or "truc tuyen" in lowered:
        return "ONLINE"
    if "counter" in lowered or "tại quầy" in lowered or "tai quay" in lowered or "quầy" in lowered:
        return "COUNTER"
    return None


def extract_supplemental_params(user_message: str, pending_tool_context: dict) -> dict:
    missing_fields = set(pending_tool_context.get("missing_fields") or [])
    text = user_message.strip()
    extracted = {}

    month_value = extract_month_value(text)
    if month_value is not None:
        if "term_month" in missing_fields:
            extracted["term_month"] = month_value
        if "duration_month" in missing_fields:
            extracted["duration_month"] = month_value

    amount_phrase = extract_amount_phrase(text)
    amount_value = coerce_float(amount_phrase) if amount_phrase else None
    if amount_value is not None:
        if "amount" in missing_fields:
            extracted["amount"] = amount_value
        if "total_amount" in missing_fields:
            extracted["total_amount"] = amount_value
        if "goal_amount" in missing_fields:
            extracted["goal_amount"] = amount_value

    channel = extract_channel_value(text)
    if channel:
        extracted["channel"] = channel
        extracted["prefer_rate"] = channel

    return extracted


async def run_pending_tool_if_supplemented(
        user_message: str,
        pending_tool_context: dict | None,
        session: Session,
        bank_service: BankService,
        saving_plan_service: SavingPlanService,
        polish_response: bool = True,
) -> tuple[str, list[dict]] | None:
    if not pending_tool_context:
        return None

    function_name = pending_tool_context.get("name")
    if function_name not in TOOL_NAMES:
        return None

    supplemental_params = extract_supplemental_params(user_message, pending_tool_context)
    if not supplemental_params:
        return None

    merged_arguments = {
        **(pending_tool_context.get("arguments") or {}),
        **supplemental_params,
    }
    tool_result = await execute_tool_arguments(
        function_name,
        merged_arguments,
        session,
        bank_service,
        saving_plan_service,
        tool_call_id="pending_tool_context",
    )
    answer = canonical_tool_answer(tool_result["result"])
    if polish_response:
        answer = polish_backend_answer(user_message, answer)
    return answer, [tool_result]


# =============================================================================
# 6. Prompt Context Builders
# =============================================================================

def format_history_for_agent(history_messages: list[dict[str, str]]) -> str:
    if not history_messages:
        return ""

    # lấy 8 tin nhắn và trả lời của user và hệ thống gần nhất
    lines = []
    for message in history_messages[-8:]:
        lines.append(f"{message['role']}: {message['content']}")
    return "\n".join(lines)


def format_pending_tool_context(pending_tool_context: dict | None) -> str:
    if not pending_tool_context:
        return ""

    return json.dumps(
        {
            "pending_function": pending_tool_context.get("name"),
            "known_arguments": pending_tool_context.get("arguments") or {},
            "missing_fields": pending_tool_context.get("missing_fields") or [],
            "instruction": (
                "Nguoi dung dang bo sung thong tin cho function dang cho. "
                "Hay merge thong tin moi voi known_arguments va goi lai pending_function. "
                "Chi hoi lai neu backend van tra missing_fields sau khi goi tool."
            ),
        },
        ensure_ascii=False,
        default=json_default,
    )


def format_rate_answer(params: dict, rows: list[dict]) -> str:
    limit = min(int(params.get("limit") or MAX_RATE_ROWS_FOR_LLM), MAX_RATE_ROWS_FOR_LLM)
    sort = params.get("sort")
    codes = params.get("codes") or []
    unique_bank = sort == "highest" or len(codes) != 1
    compacted = compact_rate_rows(rows, limit=limit, unique_bank=unique_bank)

    if not compacted:
        term_text = f" kỳ hạn {params.get('term_month')} tháng" if params.get("term_month") else ""
        return f"Hiện tại tôi chưa tìm thấy dữ liệu lãi suất{term_text} phù hợp."

    best = compacted[0]
    term_text = f" kỳ hạn {params.get('term_month')} tháng" if params.get("term_month") else ""

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
            second = compacted[1]
            difference = round(float(best["rate"]) - float(second["rate"]), 2)
            lines.append(
                f"Chênh lệch giữa {best['code']} và {second['code']} là {difference}%/năm."
            )
        return "\n".join(lines)

    if sort == "compare" or len(codes) > 1:
        lines = [f"So sánh lãi suất{term_text}:"]
    else:
        lines = [f"Lãi suất{term_text}:"]

    for item in compacted:
        lines.append(f"- {item['code']}: {item['rate']}%/năm, kỳ hạn {item['term_month']} tháng")

    if sort == "compare" or len(codes) > 1:
        lines.append(f"Kết luận: {best['code']} đang có lãi suất cao nhất trong nhóm trên.")
        if len(compacted) > 1:
            second = compacted[1]
            difference = round(float(best["rate"]) - float(second["rate"]), 2)
            lines.append(
                f"Chênh lệch giữa {best['code']} và {second['code']} là {difference}%/năm."
            )

    return "\n".join(lines)


def build_polish_messages(user_message: str, backend_answer: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "Bạn chỉ biên tập câu trả lời tiếng Việt cho tự nhiên hơn. "
                "Không thêm, không bỏ, không đổi bất kỳ số liệu, mã ngân hàng, kỳ hạn, "
                "thứ hạng, kết luận hoặc chênh lệch nào. Nếu không chắc, trả lại nguyên văn."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Câu hỏi người dùng: {user_message}\n"
                f"Câu trả lời backend cần giữ nguyên dữ liệu:\n{backend_answer}"
            ),
        },
    ]


def polish_backend_answer(user_message: str, backend_answer: str) -> str:
    try:
        response = create_chat_completion_with_retry(
            messages=build_polish_messages(user_message, backend_answer),
            initial_temperature=0,
        )
    except Exception:
        return backend_answer

    polished = (response.choices[0].message.content or "").strip()
    return polished or backend_answer


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
    plan_text = (
        f"Kế hoạch #{result.get('plan_id')}"
        if result.get("plan_id")
        else "Phương án đề xuất"
    )
    return (
        f"{plan_text} dùng thuật toán {result.get('algorithm_used')}. "
        f"Số tiền cuối kỳ dự kiến: {result.get('final_amount', 0):,.0f} VND, "
        f"lãi đạt được: {result.get('achieved_interest', 0):,.0f} VND, {goal_text}."
    )


def format_compare_interest_answer(result: dict) -> str:
    if result.get("missing_fields"):
        missing_labels = {
            "term_month": "kỳ hạn gửi",
            "amount": "số tiền gửi",
        }
        missing = ", ".join(missing_labels.get(field, field) for field in result["missing_fields"])
        matched_banks = result.get("matched_banks") or []
        bank_text = ""
        if matched_banks:
            bank_text = " cho " + " và ".join(
                str(bank.get("code") or bank.get("name") or "ngân hàng")
                for bank in matched_banks
            )
        return f"Bạn cần bổ sung {missing}{bank_text} để tôi tính và so sánh tiền lãi."

    if result.get("error"):
        return result["error"]

    calculations = result.get("calculations") or []
    if not calculations:
        return "Hiện tại tôi chưa có đủ dữ liệu để so sánh tiền lãi giữa các ngân hàng này."

    lines = [
        (
            f"So sánh với số tiền {result.get('amount', 0):,.0f} VND, "
            f"kỳ hạn {result.get('term_month')} tháng, kênh {result.get('channel')}:"
        )
    ]
    for item in sorted(calculations, key=lambda row: row.get("total_amount", 0), reverse=True):
        lines.append(
            f"- {item['bank_name']}: lãi suất {item['interest_rate']}%/năm, "
            f"tiền lãi {item['interest_amount']:,.0f} VND, "
            f"tổng nhận {item['total_amount']:,.0f} VND."
        )

    if result.get("better_bank"):
        lines.append(
            f"Kết luận: {result['better_bank']} tốt hơn, chênh lệch tiền lãi khoảng "
            f"{result.get('difference_interest_amount', 0):,.0f} VND."
        )

    return "\n".join(lines)


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


def canonical_tool_answer(result_context: dict) -> str:
    if result_context.get("fallback_answer"):
        return result_context["fallback_answer"]
    return fallback_context_answer(result_context)


# =============================================================================
# 8. Domain Tool Implementations
# =============================================================================

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
            "error": "Không tìm thấy ngân hàng phù hợp. Vui lòng cung cấp mã hoặc tên ngân hàng chính xác."
        }

    deposit_date = parse_iso_date(args.get("deposit_date")) or date.today()

    request = InterestCalculateRequest(
        bank_id=resolved_bank_id,
        channel=(args.get("channel") or "ONLINE").upper(),
        term_month=args["term_month"],
        amount=args["amount"],
        deposit_date=deposit_date,
    )

    return bank_service.calculate_interest(request).model_dump()


def create_saving_plan(saving_plan_service: SavingPlanService, args: dict):
    duration_month = args["duration_month"]
    total_amount = args["total_amount"]
    goal_amount = args.get("goal_amount") or total_amount

    request = SavingPlanCreate(
        name=args.get("name") or "Kế hoạch tiết kiệm từ chatbot",
        duration_month=duration_month,
        total_amount=total_amount,
        goal_amount=goal_amount,
        prefer_rate=(args.get("prefer_rate") or "ONLINE").upper(),
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
        if params.get("name") and params["name"] not in names:
            names.append(params["name"])
        if params.get("code") and params["code"] not in codes:
            codes.append(params["code"])

        limit = min(params.get("limit") or MAX_RATE_ROWS_FOR_LLM, MAX_RATE_ROWS_FOR_LLM)
        if params.get("sort") == "highest" and not codes and not names:
            rows = bank_service.get_top_rates_for_chatbot(
                term_month=params.get("term_month"),
                channel=params.get("channel"),
                amount=params.get("amount"),
                limit=limit,
            )
        else:
            rows = bank_service.get_rates_for_chatbot(
                codes=codes,
                names=names,
                term_month=params.get("term_month"),
                channel=params.get("channel"),
                amount=params.get("amount"),
                limit=limit,
            )
        return {
            "type": "rate_lookup",
            "params": params,
            "rates": rows,
            "fallback_answer": format_rate_answer(params, rows),
        }

    if intent == "calculate_deposit_interest":
        missing_fields = []
        if not any([params.get("bank_id"), params.get("bank_code"), params.get("bank_name")]):
            missing_fields.append("bank")
        if params.get("term_month") is None:
            missing_fields.append("term_month")
        if params.get("amount") is None:
            missing_fields.append("amount")

        if missing_fields:
            return {
                "type": "calculate_deposit_interest",
                "missing_fields": missing_fields,
                "message": "Cần ngân hàng, kỳ hạn và số tiền gửi để tính tiền lãi.",
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
        deposit_date_value = parse_iso_date(params.get("deposit_date"))
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
            "fallback_answer": format_compare_interest_answer(result),
        }

    if intent == "create_saving_plan":
        missing_fields = []
        if params.get("duration_month") is None:
            missing_fields.append("duration_month")
        if params.get("total_amount") is None:
            missing_fields.append("total_amount")

        if missing_fields:
            return {
                "type": "create_saving_plan",
                "missing_fields": missing_fields,
                "message": "Cần thời gian kế hoạch và số tiền ban đầu để lập kế hoạch tiết kiệm.",
            }

        try:
            result = create_saving_plan(saving_plan_service, params)
        except Exception as e:
            result = {"error": str(e)}
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


# =============================================================================
# 9. Agent Message Assembly
# =============================================================================

def build_agent_messages(
        user_message: str,
        history_messages: list[dict[str, str]] | None = None,
        pending_tool_context: dict | None = None,
) -> list[dict[str, str]]:
    # build message bao gồm 3 phần hệ thống, lịch sử, hiện tại
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    pending_context_text = format_pending_tool_context(pending_tool_context)
    if pending_context_text:
        messages.append({
            "role": "system",
            "content": (
                "Pending tool context từ lượt trước:\n"
                f"{pending_context_text}\n"
                "Nếu tin nhắn hiện tại chỉ là thông tin bổ sung như số tiền, kỳ hạn, "
                "kênh gửi hoặc mục tiêu, hãy dùng pending_function thay vì xem là câu hỏi mới."
            ),
        })
    history_text = format_history_for_agent(history_messages or [])
    if history_text:
        messages.append({
            "role": "system",
            "content": f"Context hội thoại gần đây:\n{history_text}",
        })
    messages.append({"role": "user", "content": user_message})
    return messages


# =============================================================================
# 10. Tool Runtime
# =============================================================================

def assistant_tool_call_message(response_message) -> dict:
    return {
        "role": "assistant",
        "content": response_message.content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in response_message.tool_calls or []
        ],
    }


async def execute_tool_arguments(
        function_name: str,
        arguments: dict,
        session: Session,
        bank_service: BankService,
        saving_plan_service: SavingPlanService,
        tool_call_id: str | None = None,
) -> dict:
    if function_name not in TOOL_NAMES:
        return {
            "tool_call_id": tool_call_id,
            "name": function_name,
            "arguments": {},
            "result": {
                "type": "tool_error",
                "message": OUT_OF_SCOPE_ANSWER,
            },
        }

    params = normalize_tool_params(sanitize_tool_arguments(arguments))
    result = await execute_function_call(
        function_name,
        params,
        session,
        bank_service,
        saving_plan_service,
    )
    return {
        "tool_call_id": tool_call_id,
        "name": function_name,
        "arguments": params,
        "result": result,
    }


async def execute_tool_call(
        tool_call,
        session: Session,
        bank_service: BankService,
        saving_plan_service: SavingPlanService,
) -> dict:
    function_name = tool_call.function.name
    try:
        arguments = json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError:
        arguments = {}

    return await execute_tool_arguments(
        function_name,
        arguments,
        session,
        bank_service,
        saving_plan_service,
        tool_call_id=tool_call.id,
    )


# =============================================================================
# 11. Agent Loop
# =============================================================================

async def run_tool_calling_agent(
        user_message: str,
        history_messages: list[dict[str, str]],
        session: Session,
        bank_service: BankService,
        saving_plan_service: SavingPlanService,
        pending_tool_context: dict | None = None,
        polish_response: bool = True,
) -> tuple[str, list[dict]]:
    pending_result = await run_pending_tool_if_supplemented(
        user_message,
        pending_tool_context,
        session,
        bank_service,
        saving_plan_service,
        polish_response,
    )
    if pending_result:
        return pending_result

    messages = build_agent_messages(user_message, history_messages, pending_tool_context)
    print(f"messages: {messages}")
    tool_results = []

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = create_chat_completion_with_retry(
                messages=messages,
                use_tools=True,
                retry_system_prompt=TOOL_RETRY_SYSTEM_PROMPT,
            )
        except Exception as e:
            recovered_tool = parse_failed_tool_generation(e)
            if not recovered_tool:
                raise

            function_name, arguments = recovered_tool
            print(f"[Recovered malformed tool call] {function_name}: {arguments}")
            tool_result = await execute_tool_arguments(
                function_name,
                arguments,
                session,
                bank_service,
                saving_plan_service,
                tool_call_id="recovered_tool_call",
            )
            tool_results.append(tool_result)
            answer = canonical_tool_answer(tool_result["result"])
            if polish_response:
                answer = polish_backend_answer(user_message, answer)
            return answer, tool_results

        response_message = response.choices[0].message

        print(f"response: {response_message}")

        if not response_message.tool_calls:
            return response_message.content or OUT_OF_SCOPE_ANSWER, tool_results

        messages.append(assistant_tool_call_message(response_message))

        for tool_call in response_message.tool_calls:

            print(f"tool_call: {tool_call}")
            tool_result = await execute_tool_call(
                tool_call,
                session,
                bank_service,
                saving_plan_service,
            )
            tool_results.append(tool_result)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result["result"], ensure_ascii=False, default=json_default),
            })
            if tool_result["result"].get("fallback_answer") or tool_result["result"].get("message"):
                answer = canonical_tool_answer(tool_result["result"])
                if polish_response:
                    answer = polish_backend_answer(user_message, answer)
                return answer, tool_results

    return fallback_context_answer(tool_results[-1]["result"]) if tool_results else OUT_OF_SCOPE_ANSWER, tool_results


# =============================================================================
# 12. Conversation Turn Lifecycle
# =============================================================================

def create_agent_services(session) -> tuple[BankService, SavingPlanService, ChatbotConversationService]:
    return (
        BankService(session),
        SavingPlanService(session),
        ChatbotConversationService(session),
    )


def prepare_conversation_turn(
        conversation_service: ChatbotConversationService,
        user_message: str,
        user_id: int | None,
        use_context: bool,
):
    conversation = None
    history_messages = []
    pending_tool_context = None

    if use_context:
        conversation = conversation_service.get_or_create_user_conversation(
            user_id=user_id,
            title=user_message[:240],
        )
        history_messages = conversation_service.build_context_messages(conversation.id, limit=20)
        pending_tool_context = conversation_service.build_pending_tool_context(conversation.id)
        conversation_service.add_user_message(conversation.id, user_message)

    return conversation, history_messages, pending_tool_context


def save_conversation_turn(
        conversation_service: ChatbotConversationService,
        use_context: bool,
        conversation,
        answer: str,
        tool_results: list[dict],
) -> None:
    if use_context and conversation:
        conversation_service.add_assistant_message(
            conversation.id,
            answer,
            intent=tool_results[-1]["name"] if tool_results else "out_of_scope",
            message_metadata=to_jsonable({
                "tool_results": tool_results,
            }),
        )
        conversation_service.commit()


async def stream_final_answer_chunks(
        user_message: str,
        canonical_answer: str,
        use_llm_stream: bool,
):
    if use_llm_stream:
        try:
            stream = create_chat_completion_stream(
                build_polish_messages(user_message, canonical_answer),
                initial_temperature=0,
            )
            for chunk in iter_stream_content_chunks(stream):
                yield chunk
                await asyncio.sleep(0)
            return
        except Exception as e:
            print(f"[Final Answer Stream Error] {e}")

    for chunk in split_text_chunks(canonical_answer):
        yield chunk
        await asyncio.sleep(0.02)


# =============================================================================
# 13. Public Agent Entry Points
# =============================================================================

async def run_agent(
        user_message: str,
        session,
        user_id: int | None = None,
        use_context: bool = True,
) -> dict:
    bank_service, saving_plan_service, conversation_service = create_agent_services(session)

    print(f"\n{'='*60}")
    print(f"user: {user_message}")
    print(f"\n{'='*60}")

    conversation = None

    try:
        conversation, history_messages, pending_tool_context = prepare_conversation_turn(
            conversation_service,
            user_message,
            user_id,
            use_context,
        )
        answer, tool_results = await run_tool_calling_agent(
            user_message,
            history_messages,
            session,
            bank_service,
            saving_plan_service,
            pending_tool_context,
        )
        print(f"\n[Tool Results] {json.dumps(tool_results, ensure_ascii=False, default=json_default)}")

        save_conversation_turn(
            conversation_service,
            use_context,
            conversation,
            answer,
            tool_results,
        )
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


async def stream_agent_answer(
        user_message: str,
        session,
        user_id: int | None = None,
        use_context: bool = True,
) -> AsyncGenerator[str, None]:
    bank_service, saving_plan_service, conversation_service = create_agent_services(session)

    conversation = None
    answer = ""

    try:
        conversation, history_messages, pending_tool_context = prepare_conversation_turn(
            conversation_service,
            user_message,
            user_id,
            use_context,
        )
        answer, tool_results = await run_tool_calling_agent(
            user_message,
            history_messages,
            session,
            bank_service,
            saving_plan_service,
            pending_tool_context,
            polish_response=False,
        )

        streamed_answer_parts = []
        async for chunk in stream_final_answer_chunks(
                user_message,
                answer,
                use_llm_stream=bool(tool_results),
        ):
            streamed_answer_parts.append(chunk)
            yield encode_stream_event("chunk", {
                "conversation_id": conversation.id if conversation else None,
                "chunk": chunk,
            })

        streamed_answer = "".join(streamed_answer_parts).strip()
        if streamed_answer:
            answer = streamed_answer

        save_conversation_turn(
            conversation_service,
            use_context,
            conversation,
            answer,
            tool_results,
        )
    except Exception as e:
        print(f"[Stream Agent Error] {e}")
        conversation_service.rollback()
        conversation = None
        answer = OUT_OF_SCOPE_ANSWER
        for chunk in split_text_chunks(answer):
            yield encode_stream_event("chunk", {
                "conversation_id": None,
                "chunk": chunk,
            })
            await asyncio.sleep(0.02)

    yield encode_stream_event("done", {
        "conversation_id": conversation.id if conversation else None,
        "answer": answer,
    })
