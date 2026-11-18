"""
门户业务编排。

客户视角：按请求头里的客户号去调中台，只读写本人数据。
管理员视角：列表和大盘走 finance 库只读查询，审批/工单处理复用中台既有写接口，
并保持员工身份（X-Operator-No）以便中台侧留痕。
"""
import uuid

from assistant.conf.config import settings
from assistant.repository import portal_queries
from assistant.utils.finance_client import FinanceError, finance_request
from assistant.utils.finance_readonly_db import ensure_contract_document


def _request_no() -> str:
    return str(uuid.uuid4())


async def get_defaults() -> dict:
    return {
        "demo_customer_no": settings.demo_customer_no,
        "operator_no": settings.finance_operator_no,
        "channel_code": settings.finance_channel_code,
    }


# ---------------------------------------------------------------- 客户视角


async def get_me(customer_no: str) -> dict:
    profile = await finance_request(
        "GET", f"/customers/{customer_no}", customer_no=customer_no
    )
    accounts = await portal_queries.list_accounts(customer_no)
    limits = await portal_queries.list_credit_limits(customer_no)
    loans = await portal_queries.customer_loan_applications(customer_no, 1, 3)
    tickets = await portal_queries.customer_tickets(customer_no, 1, 3)

    total_balance = sum(float(item.get("balance_amount") or 0) for item in accounts)
    available_limit = sum(float(item.get("available_limit_amount") or 0) for item in limits)
    return {
        "profile": profile,
        "summary": {
            "account_count": len(accounts),
            "total_balance": f"{total_balance:.2f}",
            "available_limit": f"{available_limit:.2f}",
            "loan_count": loans["total"],
            "ticket_count": tickets["total"],
        },
        "recent_loans": loans["items"],
        "recent_tickets": tickets["items"],
    }


async def get_accounts(customer_no: str, account_status: str = "") -> dict:
    items = await portal_queries.list_accounts(customer_no, account_status)
    return {"items": items, "total": len(items)}


async def get_transactions(
    customer_no: str,
    account_no: str,
    *,
    page_no: int = 1,
    page_size: int = 20,
    start_time: str = "",
    end_time: str = "",
    transaction_type: str = "",
) -> dict:
    params: dict = {
        "page_no": page_no,
        "page_size": page_size,
    }
    if start_time:
        params["start_time"] = start_time
    if end_time:
        params["end_time"] = end_time
    if transaction_type:
        params["transaction_type"] = transaction_type
    data = await finance_request(
        "GET",
        f"/accounts/{account_no}/transactions",
        customer_no=customer_no,
        params=params,
    )
    return {
        "items": data.get("list") or [],
        "total": data.get("total_count") or 0,
        "page_no": data.get("page_no") or page_no,
        "page_size": data.get("page_size") or page_size,
    }


async def get_credit_limits(customer_no: str) -> dict:
    items = await portal_queries.list_credit_limits(customer_no)
    return {"items": items, "total": len(items)}


async def get_loan_applications(customer_no: str, page_no: int, page_size: int) -> dict:
    return await portal_queries.customer_loan_applications(customer_no, page_no, page_size)


async def submit_loan_application(customer_no: str, payload: dict) -> dict:
    body = {
        "request_no": payload.get("request_no") or _request_no(),
        "customer_no": customer_no,
        "limit_no": payload["limit_no"],
        "apply_amount": str(payload["apply_amount"]),
        "apply_term_months": int(payload["apply_term_months"]),
        "repayment_method": payload["repayment_method"],
        "loan_purpose": payload.get("loan_purpose") or "日常消费",
        "materials": [],
    }
    return await finance_request(
        "POST", "/loan/applications", customer_no=customer_no, json_body=body
    )


async def get_tickets(customer_no: str, page_no: int, page_size: int) -> dict:
    return await portal_queries.customer_tickets(customer_no, page_no, page_size)


async def create_ticket(customer_no: str, payload: dict) -> dict:
    body = {
        "request_no": payload.get("request_no") or _request_no(),
        "customer_no": customer_no,
        "ticket_type": payload.get("ticket_type") or "complaint",
        "ticket_title": payload.get("ticket_title") or "客户工单",
        "ticket_content": payload["ticket_content"],
        "related_type": payload.get("related_type") or "none",
    }
    if payload.get("related_id"):
        body["related_id"] = int(payload["related_id"])
    return await finance_request(
        "POST",
        "/support/tickets",
        customer_no=customer_no,
        with_operator=True,
        json_body=body,
    )


async def get_wealth_positions(customer_no: str) -> dict:
    data = await finance_request(
        "GET", f"/customers/{customer_no}/wealth/positions", customer_no=customer_no
    )
    items = data.get("list") or []
    return {"items": items, "total": len(items)}


# ---------------------------------------------------------------- 管理员视角


async def admin_overview() -> dict:
    overview = await portal_queries.overview()
    overview["recent_loans"] = (
        await portal_queries.list_loan_applications("submitted", "", 1, 5)
    )["items"]
    overview["recent_tickets"] = (
        await portal_queries.list_tickets("processing", "", 1, 5)
    )["items"]
    return overview


async def admin_customers(keyword: str, page_no: int, page_size: int) -> dict:
    return await portal_queries.list_customers(keyword, page_no, page_size)


async def admin_customer_detail(
    customer_no: str, operator_no: str | None = None
) -> dict:
    operator_no = operator_no or settings.finance_operator_no
    profile = await finance_request(
        "GET", f"/customers/{customer_no}", customer_no=operator_no
    )
    accounts = await portal_queries.list_accounts(customer_no)
    limits = await portal_queries.list_credit_limits(customer_no)
    transactions = await portal_queries.recent_transactions(customer_no, 10)
    tickets = await portal_queries.customer_tickets(customer_no, 1, 5)
    loans = await portal_queries.customer_loan_applications(customer_no, 1, 5)
    return {
        "profile": profile,
        "accounts": accounts,
        "credit_limits": limits,
        "transactions": transactions,
        "tickets": tickets["items"],
        "loan_applications": loans["items"],
    }


async def admin_loan_applications(
    status: str, keyword: str, page_no: int, page_size: int
) -> dict:
    result = await portal_queries.list_loan_applications(
        status, keyword, page_no, page_size
    )
    result["status_counts"] = await portal_queries.loan_status_counts()
    return result


async def admin_loan_decision(
    application_no: str, payload: dict, operator_no: str | None = None
) -> dict:
    operator_no = operator_no or settings.finance_operator_no
    application = await portal_queries.get_loan_application(application_no)
    if not application:
        raise FinanceError("未找到该贷款申请，请刷新后重试。")

    decision = payload.get("decision")
    if decision not in {"approved", "rejected"}:
        raise FinanceError("审批结果只能是 approved 或 rejected。")

    body = {
        "request_no": payload.get("request_no") or _request_no(),
        "approval_node": payload.get("approval_node") or "final_review",
        "approval_result": decision,
        "approved_amount": str(
            payload.get("approved_amount") or application["apply_amount"]
        ),
        "approved_rate": str(
            payload.get("approved_rate") or application["annual_interest_rate"]
        ),
        "approved_term_months": int(
            payload.get("approved_term_months") or application["apply_term_months"]
        ),
        "approval_comment": payload.get("approval_comment") or "",
    }
    result = await finance_request(
        "POST",
        f"/loan/applications/{application_no}/approval-records",
        customer_no=operator_no,
        with_operator=True,
        json_body=body,
    )
    data = dict(result or {})
    if decision == "approved":
        # 中台审批只生成待签约合同，额度会一直冻结；这里补签约与放款，把冻结转为已用。
        data["auto_disbursement"] = await _auto_disburse(application_no, operator_no)
    return data


async def _auto_disburse(application_no: str, operator_no: str) -> dict:
    """审批通过后自动完成签约与全额放款，失败时只返回原因，不影响已通过的审批。"""
    try:
        contract = await portal_queries.get_contract_for_application(application_no)
        if not contract:
            return {"status": "skipped", "message": "未找到审批生成的合同。"}
        if contract["contract_status"] not in {"pending_sign", "signed"}:
            return {"status": "skipped", "message": "合同状态无需自动放款。"}
        if contract["contract_status"] == "pending_sign":
            document_no = await ensure_contract_document(int(contract["id"]))
            await finance_request(
                "POST",
                f"/loan/contracts/{contract['contract_no']}/sign-records",
                customer_no=operator_no,
                with_operator=True,
                json_body={
                    "request_no": _request_no(),
                    "document_no": document_no,
                    "signer_type": "customer",
                    "signer_name": contract["customer_name"] or "客户",
                    "sign_method": "electronic",
                    "sign_result": "signed",
                },
            )
        if not contract["repayment_account_no"]:
            return {"status": "failed", "message": "合同未绑定还款账户，无法放款。"}
        amount = contract["undisbursed_principal_amount"]
        await finance_request(
            "POST",
            f"/loan/contracts/{contract['contract_no']}/disbursements",
            customer_no=operator_no,
            with_operator=True,
            json_body={
                "request_no": _request_no(),
                "account_no": contract["repayment_account_no"],
                "disbursement_amount": str(amount),
            },
        )
        return {
            "status": "success",
            "contract_no": contract["contract_no"],
            "amount": str(amount),
        }
    except (FinanceError, RuntimeError) as exc:
        return {"status": "failed", "message": str(exc)}


async def _create_ticket_task(ticket: dict, operator_no: str) -> str:
    """为没有流程任务的历史工单补建流程，返回新生成的待办任务号。"""
    created = await finance_request(
        "POST",
        "/workflow/instances",
        customer_no=operator_no,
        with_operator=True,
        json_body={
            "request_no": _request_no(),
            "workflow_type": "support_ticket",
            "related_type": "support_ticket",
            "related_id": int(ticket["ticket_id"]),
            "initiator_type": "employee",
            "initiator_no": operator_no,
        },
    )
    instance_no = created.get("instance_no")
    if not instance_no:
        raise FinanceError("工单流程创建失败，请稍后重试。")
    detail = await finance_request(
        "GET",
        f"/workflow/instances/{instance_no}",
        customer_no=operator_no,
        with_operator=True,
    )
    for task in detail.get("tasks") or []:
        if task.get("task_status") in {"pending", "processing"}:
            return str(task["task_no"])
    raise FinanceError("工单流程创建成功但没有生成待办任务，请刷新后重试。")


async def admin_tickets(status: str, keyword: str, page_no: int, page_size: int) -> dict:
    result = await portal_queries.list_tickets(status, keyword, page_no, page_size)
    result["status_counts"] = await portal_queries.ticket_status_counts()
    return result


async def admin_ticket_decision(
    ticket_no: str, payload: dict, operator_no: str | None = None
) -> dict:
    operator_no = operator_no or settings.finance_operator_no
    ticket = await portal_queries.get_ticket_with_task(ticket_no)
    if not ticket:
        raise FinanceError("未找到该工单，请刷新后重试。")

    decision = payload.get("decision")
    if decision not in {"approved", "rejected"}:
        raise FinanceError("处理结果只能是 approved 或 rejected。")

    task_no = ticket.get("pending_task_no")
    if not task_no:
        # 历史测试数据只有工单、没有流程任务，这里补建流程后再完成待办，
        # 让管理员在一套工作台上就能处理全部工单。
        if ticket["ticket_status"] not in {"submitted", "processing"}:
            raise FinanceError("该工单已办结，无需重复处理。")
        task_no = await _create_ticket_task(ticket, operator_no)

    return await finance_request(
        "POST",
        f"/workflow/tasks/{task_no}/complete",
        customer_no=operator_no,
        with_operator=True,
        json_body={
            "request_no": payload.get("request_no") or _request_no(),
            "task_result": decision,
            "task_comment": payload.get("task_comment") or "",
        },
    )
