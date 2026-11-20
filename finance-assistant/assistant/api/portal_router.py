"""
门户 BFF 接口。

前端通过 X-Customer-No / X-Operator-No 传当前身份，这里再按该身份调用中台，
彻底去掉对 .env 里写死客户号的依赖。
"""
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from assistant.conf.config import settings
from assistant.service import portal_service
from assistant.utils.finance_client import FinanceError

portal_router = APIRouter(prefix="/api/portal", tags=["portal"])


# ------------------------------------------------------------------ 依赖


def current_customer(
    x_customer_no: str | None = Header(default=None, alias="X-Customer-No"),
    customer_no: str | None = Query(default=None),
) -> str:
    value = (x_customer_no or customer_no or "").strip()
    if not value:
        raise HTTPException(status_code=401, detail="缺少客户身份，请先切换客户号。")
    return value


def current_operator(
    x_operator_no: str | None = Header(default=None, alias="X-Operator-No"),
) -> str:
    return (x_operator_no or settings.finance_operator_no).strip()


# ------------------------------------------------------------------ 请求模型


class LoanApplicationCreate(BaseModel):
    limit_no: str
    apply_amount: Decimal
    apply_term_months: int
    repayment_method: str
    loan_purpose: str | None = None


class TicketCreate(BaseModel):
    ticket_type: str = "complaint"
    ticket_title: str = "客户工单"
    ticket_content: str
    related_type: str = "none"
    related_id: int | None = None


class LoanDecision(BaseModel):
    decision: str
    approved_amount: Decimal | None = None
    approved_rate: Decimal | None = None
    approved_term_months: int | None = None
    approval_comment: str | None = None


class TicketDecision(BaseModel):
    decision: str
    task_comment: str | None = None


# ------------------------------------------------------------------ 工具


async def _call(func: Callable[[], Awaitable[Any]]) -> dict:
    try:
        data = await func()
    except FinanceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"code": 0, "data": data}


# ------------------------------------------------------------------ 公共


@portal_router.get("/defaults")
async def defaults() -> dict:
    return {"code": 0, "data": await portal_service.get_defaults()}


# ------------------------------------------------------------------ 客户视角


@portal_router.get("/me")
async def my_profile(customer_no: Annotated[str, Depends(current_customer)]) -> dict:
    return await _call(lambda: portal_service.get_me(customer_no))


@portal_router.get("/accounts")
async def my_accounts(
    customer_no: Annotated[str, Depends(current_customer)],
    account_status: str = Query(default=""),
) -> dict:
    return await _call(
        lambda: portal_service.get_accounts(customer_no, account_status)
    )


@portal_router.get("/accounts/{account_no}/transactions")
async def my_transactions(
    account_no: str,
    customer_no: Annotated[str, Depends(current_customer)],
    page_no: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    start_time: str = Query(default=""),
    end_time: str = Query(default=""),
    transaction_type: str = Query(default=""),
) -> dict:
    return await _call(
        lambda: portal_service.get_transactions(
            customer_no,
            account_no,
            page_no=page_no,
            page_size=page_size,
            start_time=start_time,
            end_time=end_time,
            transaction_type=transaction_type,
        )
    )


@portal_router.get("/credit-limits")
async def my_credit_limits(customer_no: Annotated[str, Depends(current_customer)]) -> dict:
    return await _call(lambda: portal_service.get_credit_limits(customer_no))


@portal_router.get("/loan-applications")
async def my_loan_applications(
    customer_no: Annotated[str, Depends(current_customer)],
    page_no: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> dict:
    return await _call(
        lambda: portal_service.get_loan_applications(customer_no, page_no, page_size)
    )


@portal_router.post("/loan-applications")
async def create_loan_application(
    body: LoanApplicationCreate,
    customer_no: Annotated[str, Depends(current_customer)],
) -> dict:
    return await _call(
        lambda: portal_service.submit_loan_application(customer_no, body.model_dump())
    )


@portal_router.get("/tickets")
async def my_tickets(
    customer_no: Annotated[str, Depends(current_customer)],
    page_no: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> dict:
    return await _call(
        lambda: portal_service.get_tickets(customer_no, page_no, page_size)
    )


@portal_router.post("/tickets")
async def create_ticket(
    body: TicketCreate,
    customer_no: Annotated[str, Depends(current_customer)],
) -> dict:
    return await _call(
        lambda: portal_service.create_ticket(customer_no, body.model_dump())
    )


@portal_router.get("/wealth/positions")
async def my_wealth_positions(customer_no: Annotated[str, Depends(current_customer)]) -> dict:
    return await _call(lambda: portal_service.get_wealth_positions(customer_no))


# ------------------------------------------------------------------ 管理员视角


@portal_router.get("/admin/overview")
async def admin_overview() -> dict:
    return await _call(portal_service.admin_overview)


@portal_router.get("/admin/customers")
async def admin_customers(
    keyword: str = Query(default=""),
    page_no: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    return await _call(
        lambda: portal_service.admin_customers(keyword, page_no, page_size)
    )


@portal_router.get("/admin/customers/{customer_no}")
async def admin_customer_detail(
    customer_no: str,
    operator_no: Annotated[str, Depends(current_operator)],
) -> dict:
    return await _call(
        lambda: portal_service.admin_customer_detail(customer_no, operator_no)
    )


@portal_router.get("/admin/loan-applications")
async def admin_loan_applications(
    status: str = Query(default=""),
    keyword: str = Query(default=""),
    page_no: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    return await _call(
        lambda: portal_service.admin_loan_applications(
            status, keyword, page_no, page_size
        )
    )


@portal_router.post("/admin/loan-applications/{application_no}/decision")
async def admin_loan_decision(
    application_no: str,
    body: LoanDecision,
    operator_no: Annotated[str, Depends(current_operator)],
) -> dict:
    return await _call(
        lambda: portal_service.admin_loan_decision(
            application_no, body.model_dump(exclude_none=True), operator_no
        )
    )


@portal_router.get("/admin/tickets")
async def admin_tickets(
    status: str = Query(default=""),
    keyword: str = Query(default=""),
    page_no: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    return await _call(
        lambda: portal_service.admin_tickets(status, keyword, page_no, page_size)
    )


@portal_router.post("/admin/tickets/{ticket_no}/decision")
async def admin_ticket_decision(
    ticket_no: str,
    body: TicketDecision,
    operator_no: Annotated[str, Depends(current_operator)],
) -> dict:
    return await _call(
        lambda: portal_service.admin_ticket_decision(
            ticket_no, body.model_dump(exclude_none=True), operator_no
        )
    )
