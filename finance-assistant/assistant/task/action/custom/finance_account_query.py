"""
账户查询 Action。

对应用户说法：查余额、查我全部账户、账户状态。
接口：
- GET /api/v1/accounts/{account_no}
- GET /api/v1/customers/{customer_no}/accounts
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

ACCOUNT_STATUS_LABELS = {
    "active": "正常",
    "frozen": "冻结",
    "closed": "已销户",
}


class QueryAccountAction(Action):
    name = "action_query_account"

    async def run(self, state: DialogueState) -> ActionResult:
        slots = active_slots(state)
        customer_no = resolve_customer_no(state)
        account_no = str(slots.get("account_no") or "").strip()
        scope = str(slots.get("account_scope") or "").strip()

        try:
            # 指定单个账户查详情，其余情况查客户账户列表
            if account_no and scope != "all":
                account = await finance_request(
                    "GET",
                    f"/accounts/{account_no}",
                    customer_no=customer_no,
                )
                return ActionResult(slots_update=self._one_account(account_no, account))

            data = await finance_request(
                "GET",
                f"/customers/{customer_no}/accounts",
                customer_no=customer_no,
            )
            accounts = data.get("list") or []
            if not accounts:
                return ActionResult(slots_update={
                    "account_summary": "您名下暂时没有可查询的账户。",
                })
            return ActionResult(slots_update=self._many_accounts(accounts))

        except Exception as exc:
            return ActionResult(slots_update={
                "error_message": str(exc),
                "account_summary": f"账户查询失败：{exc}",
            })

    def _one_account(self, account_no: str, account: dict) -> dict:
        balance = to_decimal(account.get("balance_amount"))
        frozen = to_decimal(account.get("frozen_amount"))
        available = balance - frozen
        product = account.get("account_product") or {}
        status = ACCOUNT_STATUS_LABELS.get(
            str(account.get("account_status") or ""),
            str(account.get("account_status") or "未知"),
        )
        summary = (
            f"账户 {account_no}"
            f"（{product.get('product_name', '银行账户')}）\n"
            f"余额：{money(balance)} 元\n"
            f"可用余额：{money(available)} 元\n"
            f"冻结金额：{money(frozen)} 元\n"
            f"状态：{status}"
        )
        return {
            "account_summary": summary,
            "balance_amount": money(balance),
            "available_amount": money(available),
            "frozen_amount": money(frozen),
        }

    def _many_accounts(self, accounts: list[dict]) -> dict:
        lines: list[str] = []
        for item in accounts[:10]:
            product = item.get("account_product") or {}
            lines.append(
                f"- {item.get('account_no', '-')}"
                f"（{product.get('product_name', '银行账户')}）"
                f"余额 {money(item.get('balance_amount'))} 元"
            )
        if len(accounts) > 10:
            lines.append(f"- 还有 {len(accounts) - 10} 个账户未展示")
        return {
            "account_summary": "您名下账户如下：\n" + "\n".join(lines),
            # 列表接口不返回冻结金额，清空避免与上一次查询混淆
            "balance_amount": "",
            "available_amount": "",
            "frozen_amount": "",
        }
