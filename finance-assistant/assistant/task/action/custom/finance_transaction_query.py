"""
交易流水查询 Action。

接口：GET /api/v1/accounts/{account_no}/transactions
参数：start_time、end_time、page_no、page_size（上限 100）
"""
from datetime import date, timedelta

from assistant.domain.state import DialogueState
from assistant.task.action.base import Action, ActionResult
from assistant.utils.finance_client import (
    active_slots,
    finance_request,
    money,
    normalize_date,
    resolve_customer_no,
)

TRANSACTION_TYPE_LABELS = {
    "transfer": "转账",
    "consume": "消费",
    "deposit": "存款",
    "withdraw": "取现",
    "refund": "退款",
    "adjustment": "调账",
    "wealth_income": "理财收益",
    "wealth_purchase": "理财申购",
    "wealth_redeem": "理财赎回",
    "loan_disbursement": "贷款放款",
    "loan_repayment": "贷款还款",
}

TRANSACTION_STATUS_LABELS = {
    "success": "成功",
    "failed": "失败",
    "processing": "处理中",
    "pending": "待处理",
}


class QueryTransactionsAction(Action):
    name = "action_query_transactions"

    async def run(self, state: DialogueState) -> ActionResult:
        slots = active_slots(state)
        customer_no = resolve_customer_no(state)
        account_no = str(slots.get("account_no") or "").strip()

        if not account_no:
            return ActionResult(slots_update={
                "error_message": "缺少账户号",
                "transaction_summary": "查询流水需要账户号，请先提供要查询的账户。",
            })

        default_start = (date.today() - timedelta(days=30)).isoformat()
        start = normalize_date(slots.get("transaction_start_date"), default_start)
        end = normalize_date(slots.get("transaction_end_date"), date.today().isoformat())

        try:
            data = await finance_request(
                "GET",
                f"/accounts/{account_no}/transactions",
                customer_no=customer_no,
                params={
                    "start_time": f"{start}T00:00:00",
                    "end_time": f"{end}T23:59:59",
                    "page_no": 1,
                    "page_size": 20,
                },
            )
        except Exception as exc:
            return ActionResult(slots_update={
                "error_message": str(exc),
                "transaction_summary": f"交易查询失败：{exc}",
            })

        transactions = data.get("list") or []
        total = data.get("total_count") or 0
        if not transactions:
            return ActionResult(slots_update={
                "transaction_summary": f"{start} 至 {end} 没有查询到交易记录。",
            })

        lines = [f"{start} 至 {end} 共 {total} 笔交易，最近 {min(len(transactions), 10)} 笔如下："]
        for item in transactions[:10]:
            tx_type = TRANSACTION_TYPE_LABELS.get(
                str(item.get("transaction_type") or ""),
                str(item.get("transaction_type") or "交易"),
            )
            status = TRANSACTION_STATUS_LABELS.get(
                str(item.get("transaction_status") or ""),
                str(item.get("transaction_status") or "-"),
            )
            counterparty = (
                item.get("counterparty_name")
                or item.get("merchant_name")
                or "-"
            )
            happened_at = str(item.get("transaction_at") or "")[:16]
            lines.append(
                f"- {happened_at} {tx_type} {money(item.get('transaction_amount'))} 元，"
                f"对方 {counterparty}，状态 {status}，交易号 {item.get('transaction_no', '-')}"
            )
        if total > 10:
            lines.append(f"其余 {total - 10} 笔可按更短的时间范围再查。")

        return ActionResult(slots_update={
            "transaction_summary": "\n".join(lines),
        })
