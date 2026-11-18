"""
信用卡挂失 Action。

接口：POST /api/v1/support/tickets
工单接口内部会校验员工身份，必须带 X-Operator-No。
finance-data 没有信用卡实体，卡号只作为工单内容记录。
"""
from assistant.domain.state import DialogueState
from assistant.task.action.base import Action, ActionResult
from assistant.utils.finance_client import (
    active_slots,
    finance_request,
    mask_no,
    new_request_no,
    resolve_customer_no,
)


class ReportCardLossAction(Action):
    name = "action_report_card_loss"

    async def run(self, state: DialogueState) -> ActionResult:
        slots = active_slots(state)
        customer_no = resolve_customer_no(state)

        card_no = str(slots.get("credit_card_no") or "").strip()
        loss_reason = str(slots.get("loss_reason") or "").strip()
        identity_name = str(slots.get("identity_name") or "").strip()
        id_tail = mask_no(slots.get("identity_id_no"), keep=4)

        if not card_no or not loss_reason:
            return ActionResult(slots_update={
                "loss_result": "挂失信息不完整，请提供信用卡号和挂失原因。",
            })

        content_lines = [
            f"卡号：{mask_no(card_no, keep=4)}",
            f"挂失原因：{loss_reason}",
        ]
        if identity_name:
            content_lines.append(f"持卡人：{identity_name}")
        if id_tail:
            content_lines.append(f"证件号后四位：{id_tail}")

        body = {
            "request_no": new_request_no(slots),
            "customer_no": customer_no,
            "ticket_type": "card_loss",
            "ticket_title": "信用卡挂失",
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
                "loss_result": f"挂失没有提交成功：{exc}",
            })

        ticket_no = data.get("ticket_no") or ""
        if not ticket_no:
            return ActionResult(slots_update={
                "loss_result": "挂失工单已受理，但暂时没有拿到工单号，请联系人工客服确认。",
            })

        return ActionResult(slots_update={
            "ticket_no": ticket_no,
            "loss_result": (
                f"信用卡挂失工单已提交，工单号：{ticket_no}。"
                "请尽快通过人工客服完成身份核验，避免资金风险。"
            ),
        })
