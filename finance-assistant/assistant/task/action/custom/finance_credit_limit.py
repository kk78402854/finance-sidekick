"""
贷款申请第一步：查授信额度并匹配贷款产品。

接口：
- GET /api/v1/customers/{customer_no}/credit-limits
- GET /api/v1/loan/products/{product_code}

额度列表不返回 limit_status，也不返回产品名称；
多条额度时取可用额度最大的一条，并用它的 product_code 查产品详情。
"""
from assistant.domain.state import DialogueState
from assistant.task.action.base import Action, ActionResult
from assistant.utils.finance_client import (
    active_slots,
    finance_request,
    money,
    resolve_customer_no,
    to_decimal,
)

REPAYMENT_LABELS = {
    "equal_principal_interest": "等额本息",
    "equal_principal": "等额本金",
    "interest_first": "先息后本",
}

LOAN_TYPE_LABELS = {
    "consumer": "消费贷",
    "cash": "现金贷",
    "installment": "分期贷",
    "business": "经营贷",
}

# 用户口语 -> 接口枚举
LOAN_TYPE_ALIASES = {
    "消费贷": "consumer",
    "消费": "consumer",
    "现金贷": "cash",
    "现金": "cash",
    "分期贷": "installment",
    "分期": "installment",
    "经营贷": "business",
    "经营": "business",
    "企业贷": "business",
}


def normalize_loan_type(text: str) -> str:
    """把“消费贷”“装修分期”之类口语映射成接口枚举，识别不出返回空串。"""
    for alias, value in LOAN_TYPE_ALIASES.items():
        if alias in text:
            return value
    return text if text in LOAN_TYPE_LABELS else ""


class QueryCreditLimitAction(Action):
    name = "action_query_credit_limit"

    async def run(self, state: DialogueState) -> ActionResult:
        slots = active_slots(state)
        customer_no = resolve_customer_no(state)
        amount = to_decimal(slots.get("loan_amount"))
        term = self._to_int(slots.get("loan_term_months"))

        try:
            data = await finance_request(
                "GET",
                f"/customers/{customer_no}/credit-limits",
                customer_no=customer_no,
            )
        except Exception as exc:
            return self._fail(f"授信额度查询失败：{exc}")

        limits = data.get("list") or []
        if not limits:
            return self._fail("您当前没有可用授信额度，建议先申请授信。")

        # 取可用额度最大的一条
        limit = max(limits, key=lambda item: to_decimal(item.get("available_limit_amount")))
        available = to_decimal(limit.get("available_limit_amount"))
        limit_no = str(limit.get("limit_no") or "")
        product_code = str(limit.get("product_code") or "")

        if not limit_no or not product_code:
            return self._fail("授信额度信息不完整，请联系客服。")

        if amount <= 0:
            return self._fail("贷款金额需要大于 0 元，请重新告诉我金额。")

        if amount > available:
            return self._fail(f"可用授信额度只有 {money(available)} 元，不足以申请 {money(amount)} 元。")

        try:
            detail_data = await finance_request(
                "GET",
                f"/loan/products/{product_code}",
                customer_no=customer_no,
            )
        except Exception as exc:
            return self._fail(f"贷款产品查询失败：{exc}")

        detail = detail_data.get("product_detail") or {}
        product_name = detail.get("product_name") or product_code
        min_amount = to_decimal(detail.get("min_amount"))
        max_amount = to_decimal(detail.get("max_amount"))
        min_term = self._to_int(detail.get("min_term_months"))
        max_term = self._to_int(detail.get("max_term_months"))

        if min_amount and max_amount and not (min_amount <= amount <= max_amount):
            return self._fail(
                f"申请金额超出产品范围（{money(min_amount)} ~ {money(max_amount)} 元）。"
            )

        if term <= 0:
            return self._fail("贷款期限需要大于 0 个月，请重新告诉我期限。")

        if min_term and max_term and not (min_term <= term <= max_term):
            return self._fail(f"贷款期限超出产品范围（{min_term} ~ {max_term} 个月）。")

        loan_type = str(detail.get("loan_type") or "")
        loan_type_label = LOAN_TYPE_LABELS.get(loan_type, loan_type or "贷款")

        # 额度绑定的是具体产品，用户想要的类型和产品不一致时不能混用
        wanted_type = normalize_loan_type(str(slots.get("loan_type") or ""))
        if wanted_type and loan_type and wanted_type != loan_type:
            wanted_label = LOAN_TYPE_LABELS.get(wanted_type, wanted_type)
            return self._fail(
                f"您当前可用额度对应的是{loan_type_label}产品，暂不支持办理{wanted_label}。"
                f"如需{wanted_label}，请先申请对应授信。"
            )

        repayment_method = str(detail.get("repayment_method") or "")
        repayment_label = REPAYMENT_LABELS.get(repayment_method, repayment_method or "以合同为准")

        return ActionResult(slots_update={
            "limit_no": limit_no,
            "product_code": product_code,
            "repayment_method": repayment_method,
            "credit_limit_summary": (
                f"可用额度 {money(available)} 元，产品 {product_name}（{loan_type_label}），"
                f"还款方式 {repayment_label}"
            ),
        })

    @staticmethod
    def _to_int(value) -> int:
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _fail(message: str) -> ActionResult:
        # 失败时不写 limit_no，YAML 的条件分支会直接跳到结果展示
        return ActionResult(slots_update={
            "error_message": message,
            "loan_result": message,
        })
