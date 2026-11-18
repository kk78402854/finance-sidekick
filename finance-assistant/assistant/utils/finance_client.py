"""
金融中台公共访问层。

Action 与知识 Provider 共用这里的鉴权头、错误处理和格式化函数，
避免在每个业务类里重复拼 URL、判断 code。
"""
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from assistant.conf.config import settings
from assistant.domain.state import DialogueState
from assistant.utils.httpx_client import finance_headers


class FinanceError(RuntimeError):
    """金融接口调用失败，message 已经是可直接展示给用户的中文。"""


# 接口错误码 -> 用户能看懂的话术
ERROR_MESSAGES: dict[str, str] = {
    "MISSING_AUTHORIZATION": "缺少客户身份信息，请重新登录后再试。",
    "INVALID_AUTHORIZATION": "客户身份信息格式不正确，请重新登录后再试。",
    "PRINCIPAL_NOT_FOUND": "未找到对应的客户信息，请确认客户号。",
    "CUSTOMER_NOT_FOUND": "未找到对应的客户信息，请确认客户号。",
    "ACCOUNT_NOT_FOUND": "未找到该账户，请确认账户号是否正确。",
    "CHANNEL_NOT_AVAILABLE": "当前渠道不可用，请联系客服。",
    "EMPLOYEE_NOT_AVAILABLE": "当前没有可用的客服人员，请稍后再试。",
    "CUSTOMER_SCOPE_FORBIDDEN": "只能办理本人名下的业务。",
    "CREDIT_LIMIT_NOT_ENOUGH": "可用授信额度不足，请降低申请金额。",
    "CREDIT_LIMIT_NOT_FOUND": "您当前没有可用授信额度，建议先申请授信。",
    "CREDIT_LIMIT_STATUS_FORBIDDEN": "该笔授信额度当前不可用，请换一笔额度或联系客服。",
    "LOAN_AMOUNT_OUT_OF_RANGE": "申请金额超出该产品的额度范围。",
    "LOAN_TERM_OUT_OF_RANGE": "申请期限超出该产品的期限范围。",
    "LOAN_PRODUCT_NOT_FOUND": "未找到对应的贷款产品。",
    "TRANSACTION_NOT_FOUND": "未找到该笔交易。",
    "INVALID_ARGUMENT": "提交的信息有误，请检查后重试。",
}


def active_slots(state: DialogueState) -> dict[str, Any]:
    task = state.tasks.active
    return task.slots if task else {}


def resolve_customer_no(state: DialogueState) -> str:
    """当前会话的客户号。

    优先使用前端切换身份时写入会话的客户号，
    没有才回落到 .env 的演示客户，保证旧会话仍可用。
    """
    return state.shared.customer_no or settings.demo_customer_no


async def finance_request(
    method: str,
    path: str,
    *,
    customer_no: str,
    with_operator: bool = False,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict:
    """调用金融中台接口，成功返回 data，失败抛 FinanceError。"""
    url = f"{settings.finance_api_base_url.rstrip('/')}/api/v1{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.request(
                method,
                url,
                headers=finance_headers(customer_no, with_operator=with_operator),
                params=params,
                json=json_body,
            )
    except httpx.HTTPError as exc:
        raise FinanceError("金融服务暂时不可用，请稍后再试。") from exc

    try:
        payload = resp.json()
    except Exception as exc:
        raise FinanceError(f"金融服务返回异常（HTTP {resp.status_code}）。") from exc

    # 成功时 code 是数字 0；失败时 code 是字符串错误码
    if resp.status_code >= 400 or payload.get("code") != 0:
        code = str(payload.get("code") or "")
        message = payload.get("message") or ""
        raise FinanceError(
            ERROR_MESSAGES.get(code)
            or message
            or f"金融服务处理失败（HTTP {resp.status_code}）。"
        )
    return payload.get("data") or {}


def money(value: Any) -> str:
    """金额格式化：12345.6 -> 12,345.60"""
    try:
        return f"{Decimal(str(value or '0')):,.2f}"
    except (InvalidOperation, ValueError):
        return str(value or "0.00")


def to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def new_request_no(slots: dict) -> str:
    """写接口幂等号：首次生成后写回槽位，重试时复用，避免重复提交。"""
    request_no = slots.get("request_no")
    if not request_no:
        request_no = str(uuid.uuid4())
        slots["request_no"] = request_no
    return request_no


def mask_no(value: Any, keep: int = 4) -> str:
    value = str(value or "").strip()
    if len(value) <= keep:
        return value
    return "*" * (len(value) - keep) + value[-keep:]


def normalize_date(value: Any, default: str | None = None) -> str:
    """把槽位里的日期归一化成 yyyy-MM-dd。

    LLM 已经按 Prompt 要求输出 ISO 日期，这里只做兜底，
    兼容 2026/11/01、2026.11.01、20261101 这几种写法。
    """
    raw = str(value or "").strip()
    if not raw:
        return default or date.today().isoformat()
    raw = raw.replace("/", "-").replace(".", "-")
    if len(raw) == 8 and raw.isdigit():
        raw = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw[:10]
