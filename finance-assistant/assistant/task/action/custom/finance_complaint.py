"""
投诉工单 Action。

接口：POST /api/v1/support/tickets
工单接口需要 X-Operator-No；related_type 固定 none，
用户给的交易号写进工单内容，不作为 related_id（接口要的是数据库主键）。
"""
from assistant.domain.state import DialogueState
from assistant.task.action.base import Action, ActionResult
from assistant.utils.finance_client import (
    active_slots,
    finance_request,
    new_request_no,
    resolve_customer_no,
)

TICKET_TYPE_LABELS = {
    "complaint": "complaint",
    "投诉": "complaint",
    "咨询": "consult",
    "consult": "consult",
    "建议": "suggestion",
    "suggestion": "suggestion",
    "表扬": "praise",
    "praise": "praise",
}

TICKET_TITLE_LABELS = {
    "complaint": "客户投诉",
    "consult": "业务咨询",
    "suggestion": "客户建议",
    "praise": "客户表扬",
}


class CreateComplaintTicketAction(Action):
    name = "action_create_complaint_ticket"

    async def run(self, state: DialogueState) -> ActionResult:
        slots = active_slots(state)
        customer_no = resolve_customer_no(state)

        raw_type = str(slots.get("ticket_type") or "投诉").strip()
        ticket_type = TICKET_TYPE_LABELS.get(raw_type, "complaint")
        problem_desc = str(slots.get("problem_desc") or "").strip()
        related_no = str(
            slots.get("related_transaction_no") or slots.get("transaction_no") or ""
        ).strip()

        if not problem_desc:
            return ActionResult(slots_update={
                "ticket_result": "请先描述一下具体问题，我再帮你提交工单。",
            })

        content_lines = [f"问题描述：{problem_desc}"]
        if related_no:
            content_lines.append(f"关联交易号：{related_no}")

        body = {
            "request_no": new_request_no(slots),
            "customer_no": customer_no,
            "ticket_type": ticket_type,
            "ticket_title": TICKET_TITLE_LABELS.get(ticket_type, "客户工单"),
            "ticket_content": "；".join(content_lines),
            "related_type": "none",
        }

        try:
            data = await finance_request(
                "POST",
                "/support/tickets",
                customer_no=customer_no,
                with_operator=True,
                json_body=body,
            )
        except Exception as exc:
            return ActionResult(slots_update={
                "error_message": str(exc),
                "ticket_result": f"工单没有提交成功：{exc}",
            })

        ticket_no = data.get("ticket_no") or ""
        if not ticket_no:
            return ActionResult(slots_update={
                "ticket_result": "工单已受理，但暂时没有拿到工单号，请联系人工客服确认。",
            })

        return ActionResult(slots_update={
            "ticket_no": ticket_no,
            "ticket_result": f"工单已提交，工单号：{ticket_no}。处理进度可在工单中查看。",
        })
