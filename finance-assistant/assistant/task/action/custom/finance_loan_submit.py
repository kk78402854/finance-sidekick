"""
贷款申请第二步：提交贷款申请。

接口：POST /api/v1/loan/applications
request_no 写入槽位后复用，保证重试幂等。
"""
from assistant.domain.state import DialogueState
from assistant.task.action.base import Action, ActionResult
from assistant.utils.finance_client import (
    active_slots,
    finance_request,
    new_request_no,
    resolve_customer_no,
    to_decimal,
)

APPLICATION_STATUS_LABELS = {
    "submitted": "已提交",
    "reviewing": "审批中",
    "approved": "审批通过",
    "rejected": "审批未通过",
    "cancelled": "已取消",
    "disbursed": "已放款",
}


class SubmitLoanApplicationAction(Action):
    name = "action_submit_loan_application"

    async def run(self, state: DialogueState) -> ActionResult:
        slots = active_slots(state)
        customer_no = resolve_customer_no(state)

        limit_no = str(slots.get("limit_no") or "")
        repayment_method = str(slots.get("repayment_method") or "")
        if not limit_no or not repayment_method:
            return ActionResult(slots_update={
                "loan_result": "贷款申请信息不完整，请重新提交申请。",
            })

        body = {
            "request_no": new_request_no(slots),
            "customer_no": customer_no,
            "limit_no": limit_no,
            "apply_amount": str(to_decimal(slots.get("loan_amount"))),
            "apply_term_months": int(float(str(slots.get("loan_term_months")))),
            "repayment_method": repayment_method,
            "loan_purpose": str(slots.get("loan_purpose") or "日常消费"),
            "materials": [],
        }

        try:
            data = await finance_request(
                "POST",
                "/loan/applications",
                customer_no=customer_no,
                json_body=body,
            )
        except Exception as exc:
            return ActionResult(slots_update={
                "error_message": str(exc),
                "loan_result": f"贷款申请没有提交成功：{exc}",
            })

        application_no = data.get("application_no") or ""
        if not application_no:
            return ActionResult(slots_update={
                "loan_result": "贷款申请已受理，但暂时没有拿到申请编号，请稍后在申请记录中查看。",
            })

        status = APPLICATION_STATUS_LABELS.get(
            str(data.get("application_status") or ""),
            str(data.get("application_status") or "已提交"),
        )
        return ActionResult(slots_update={
            "loan_application_no": application_no,
            "loan_result": (
                f"贷款申请已提交，申请编号：{application_no}，"
                f"当前状态：{status}。"
                "审核结果会通过消息通知你。"
            ),
        })
