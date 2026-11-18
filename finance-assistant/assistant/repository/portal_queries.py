"""
门户只读查询。

管理端列表、大盘，以及客户“我的工单/我的贷款申请”这类中台没有开放列表接口的数据，
统一在这里用只读 SELECT 查询 finance 业务库。
"""
from assistant.utils.finance_readonly_db import fetch_all, fetch_one


def _paging(page_no: int, page_size: int) -> tuple[int, int]:
    page_no = max(int(page_no or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)
    return page_size, (page_no - 1) * page_size


async def overview() -> dict:
    return await fetch_one(
        """
        SELECT
          (SELECT COUNT(*) FROM customer) AS customer_count,
          (SELECT COUNT(*) FROM customer WHERE customer_status = 'normal') AS active_customer_count,
          (SELECT COUNT(*) FROM bank_account) AS account_count,
          (SELECT COALESCE(SUM(balance_amount), 0) FROM bank_account) AS total_balance,
          (SELECT COALESCE(SUM(total_limit_amount), 0) FROM credit_limit) AS total_limit,
          (SELECT COALESCE(SUM(available_limit_amount), 0) FROM credit_limit) AS available_limit,
          (SELECT COUNT(*) FROM account_transaction) AS transaction_count,
          (SELECT COUNT(*) FROM loan_application WHERE application_status IN ('submitted', 'processing')) AS loan_pending,
          (SELECT COUNT(*) FROM support_ticket WHERE ticket_status IN ('submitted', 'processing')) AS ticket_pending
        """
    ) or {}


async def list_customers(keyword: str, page_no: int, page_size: int) -> dict:
    limit, offset = _paging(page_no, page_size)
    where = "WHERE c.customer_no LIKE :kw OR c.customer_name LIKE :kw"
    base_params = {"kw": f"%{keyword.strip()}%"} if keyword.strip() else None
    if base_params is None:
        where = ""

    total_row = await fetch_one(
        f"SELECT COUNT(*) AS total FROM customer c {where}",
        base_params,
    )
    rows = await fetch_all(
        f"""
        SELECT c.customer_no, c.customer_name, c.customer_type, c.customer_status,
               c.opened_at, rl.risk_level_name, rl.risk_level_code,
               b.branch_name
        FROM customer c
        LEFT JOIN dim_risk_level rl ON rl.id = c.risk_level_id
        LEFT JOIN dim_branch b ON b.id = c.branch_id
        {where}
        ORDER BY c.id DESC
        LIMIT {limit} OFFSET {offset}
        """,
        base_params,
    )
    return {"items": rows, "total": int((total_row or {}).get("total") or 0)}


async def list_accounts(customer_no: str, account_status: str = "") -> list[dict]:
    params: dict = {"customer_no": customer_no}
    extra = ""
    if account_status:
        extra = " AND a.account_status = :account_status"
        params["account_status"] = account_status
    return await fetch_all(
        f"""
        SELECT a.account_no, a.account_status, a.account_type, a.currency_code,
               a.balance_amount, a.frozen_amount, a.available_amount,
               a.opened_at, p.product_code, p.product_name
        FROM bank_account a
        JOIN customer c ON c.id = a.customer_id
        LEFT JOIN account_product p ON p.id = a.account_product_id
        WHERE c.customer_no = :customer_no{extra}
        ORDER BY a.opened_at DESC, a.id DESC
        """,
        params,
    )


async def list_credit_limits(customer_no: str) -> list[dict]:
    return await fetch_all(
        """
        SELECT l.limit_no, l.currency_code, l.total_limit_amount,
               l.used_limit_amount, l.frozen_limit_amount,
               l.available_limit_amount, l.limit_status, l.valid_from, l.valid_to,
               p.product_code, p.product_name, p.loan_type,
               p.annual_interest_rate, p.min_interest_rate, p.max_interest_rate,
               p.min_amount, p.max_amount, p.min_term_months, p.max_term_months,
               p.repayment_method
        FROM credit_limit l
        JOIN customer c ON c.id = l.customer_id
        JOIN loan_product p ON p.id = l.product_id
        WHERE c.customer_no = :customer_no
        ORDER BY l.limit_status, l.available_limit_amount DESC
        """,
        {"customer_no": customer_no},
    )


async def recent_transactions(customer_no: str, limit: int = 10) -> list[dict]:
    limit = min(max(int(limit), 1), 50)
    return await fetch_all(
        f"""
        SELECT t.transaction_no, t.transaction_type, t.transaction_status,
               t.transaction_amount, t.currency_code, t.counterparty_name,
               t.merchant_name, t.transaction_at
        FROM account_transaction t
        JOIN customer c ON c.id = t.customer_id
        WHERE c.customer_no = :customer_no
        ORDER BY t.transaction_at DESC, t.id DESC
        LIMIT {limit}
        """,
        {"customer_no": customer_no},
    )


async def customer_loan_applications(
    customer_no: str, page_no: int, page_size: int
) -> dict:
    limit, offset = _paging(page_no, page_size)
    total_row = await fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM loan_application a
        JOIN customer c ON c.id = a.customer_id
        WHERE c.customer_no = :customer_no
        """,
        {"customer_no": customer_no},
    )
    rows = await fetch_all(
        f"""
        SELECT a.application_no, a.apply_amount, a.apply_term_months, a.loan_purpose,
               a.application_status, a.submitted_at, a.approved_at,
               p.product_code, p.product_name, p.loan_type, p.annual_interest_rate,
               p.repayment_method
        FROM loan_application a
        JOIN customer c ON c.id = a.customer_id
        JOIN loan_product p ON p.id = a.product_id
        WHERE c.customer_no = :customer_no
        ORDER BY a.submitted_at DESC, a.id DESC
        LIMIT {limit} OFFSET {offset}
        """,
        {"customer_no": customer_no},
    )
    return {"items": rows, "total": int((total_row or {}).get("total") or 0)}


async def customer_tickets(customer_no: str, page_no: int, page_size: int) -> dict:
    limit, offset = _paging(page_no, page_size)
    total_row = await fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM support_ticket t
        JOIN customer c ON c.id = t.customer_id
        WHERE c.customer_no = :customer_no
        """,
        {"customer_no": customer_no},
    )
    rows = await fetch_all(
        f"""
        SELECT t.ticket_no, t.ticket_type, t.ticket_title, t.ticket_content,
               t.ticket_status, t.handle_result, t.submitted_at, t.handled_at
        FROM support_ticket t
        JOIN customer c ON c.id = t.customer_id
        WHERE c.customer_no = :customer_no
        ORDER BY t.submitted_at DESC, t.id DESC
        LIMIT {limit} OFFSET {offset}
        """,
        {"customer_no": customer_no},
    )
    return {"items": rows, "total": int((total_row or {}).get("total") or 0)}


async def list_loan_applications(
    status: str, keyword: str, page_no: int, page_size: int
) -> dict:
    limit, offset = _paging(page_no, page_size)
    clauses: list[str] = []
    params: dict = {}
    if status:
        clauses.append("a.application_status = :status")
        params["status"] = status
    if keyword.strip():
        clauses.append(
            "(c.customer_no LIKE :kw OR c.customer_name LIKE :kw"
            " OR a.application_no LIKE :kw)"
        )
        params["kw"] = f"%{keyword.strip()}%"
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    total_row = await fetch_one(
        f"""
        SELECT COUNT(*) AS total
        FROM loan_application a
        JOIN customer c ON c.id = a.customer_id
        {where}
        """,
        params,
    )
    rows = await fetch_all(
        f"""
        SELECT a.application_no, a.apply_amount, a.apply_term_months, a.loan_purpose,
               a.application_status, a.submitted_at,
               c.customer_no, c.customer_name,
               p.product_code, p.product_name, p.loan_type,
               p.annual_interest_rate, p.min_interest_rate, p.max_interest_rate,
               p.repayment_method
        FROM loan_application a
        JOIN customer c ON c.id = a.customer_id
        JOIN loan_product p ON p.id = a.product_id
        {where}
        ORDER BY a.submitted_at DESC, a.id DESC
        LIMIT {limit} OFFSET {offset}
        """,
        params,
    )
    return {"items": rows, "total": int((total_row or {}).get("total") or 0)}


async def loan_status_counts() -> dict[str, int]:
    rows = await fetch_all(
        "SELECT application_status AS status, COUNT(*) AS cnt"
        " FROM loan_application GROUP BY application_status"
    )
    return {str(row["status"]): int(row["cnt"]) for row in rows}


async def get_loan_application(application_no: str) -> dict | None:
    return await fetch_one(
        """
        SELECT a.application_no, a.apply_amount, a.apply_term_months, a.loan_purpose,
               a.application_status, a.submitted_at,
               c.customer_no, c.customer_name,
               p.product_code, p.product_name, p.loan_type,
               p.annual_interest_rate, p.min_interest_rate, p.max_interest_rate,
               p.repayment_method
        FROM loan_application a
        JOIN customer c ON c.id = a.customer_id
        JOIN loan_product p ON p.id = a.product_id
        WHERE a.application_no = :application_no
        """,
        {"application_no": application_no},
    )


async def list_tickets(status: str, keyword: str, page_no: int, page_size: int) -> dict:
    limit, offset = _paging(page_no, page_size)
    clauses: list[str] = []
    params: dict = {}
    if status:
        clauses.append("t.ticket_status = :status")
        params["status"] = status
    if keyword.strip():
        clauses.append(
            "(c.customer_no LIKE :kw OR c.customer_name LIKE :kw"
            " OR t.ticket_no LIKE :kw OR t.ticket_title LIKE :kw)"
        )
        params["kw"] = f"%{keyword.strip()}%"
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    total_row = await fetch_one(
        f"""
        SELECT COUNT(*) AS total
        FROM support_ticket t
        JOIN customer c ON c.id = t.customer_id
        {where}
        """,
        params,
    )
    rows = await fetch_all(
        f"""
        SELECT t.ticket_no, t.ticket_type, t.ticket_title, t.ticket_content,
               t.ticket_status, t.handle_result, t.submitted_at, t.handled_at,
               c.customer_no, c.customer_name,
               e.employee_name AS assignee_name,
               (
                 SELECT wt.task_no
                 FROM workflow_instance wi
                 JOIN workflow_task wt ON wt.instance_id = wi.id
                 WHERE wi.related_type = 'support_ticket'
                   AND wi.related_id = t.id
                   AND wt.task_status IN ('pending', 'processing')
                 ORDER BY wt.id
                 LIMIT 1
               ) AS pending_task_no
        FROM support_ticket t
        JOIN customer c ON c.id = t.customer_id
        LEFT JOIN dim_employee e ON e.id = t.assignee_id
        {where}
        ORDER BY t.submitted_at DESC, t.id DESC
        LIMIT {limit} OFFSET {offset}
        """,
        params,
    )
    return {"items": rows, "total": int((total_row or {}).get("total") or 0)}


async def ticket_status_counts() -> dict[str, int]:
    rows = await fetch_all(
        "SELECT ticket_status AS status, COUNT(*) AS cnt"
        " FROM support_ticket GROUP BY ticket_status"
    )
    return {str(row["status"]): int(row["cnt"]) for row in rows}


async def get_ticket_with_task(ticket_no: str) -> dict | None:
    return await fetch_one(
        """
        SELECT t.id AS ticket_id, t.ticket_no, t.ticket_type, t.ticket_title,
               t.ticket_status, c.customer_no, c.customer_name,
               (
                 SELECT wt.task_no
                 FROM workflow_instance wi
                 JOIN workflow_task wt ON wt.instance_id = wi.id
                 WHERE wi.related_type = 'support_ticket'
                   AND wi.related_id = t.id
                   AND wt.task_status IN ('pending', 'processing')
                 ORDER BY wt.id
                 LIMIT 1
               ) AS pending_task_no
        FROM support_ticket t
        JOIN customer c ON c.id = t.customer_id
        WHERE t.ticket_no = :ticket_no
        """,
        {"ticket_no": ticket_no},
    )


async def get_contract_for_application(application_no: str) -> dict | None:
    return await fetch_one(
        """
        SELECT contract.id,
               contract.contract_no,
               contract.contract_status,
               contract.currency_code,
               contract.principal_amount,
               contract.undisbursed_principal_amount,
               account.account_no AS repayment_account_no,
               customer.customer_name
        FROM loan_contract AS contract
        JOIN customer ON customer.id = contract.customer_id
        LEFT JOIN bank_account AS account
               ON account.id = contract.repayment_account_id
        WHERE contract.application_id = (
            SELECT id FROM loan_application WHERE application_no = :application_no
        )
        ORDER BY contract.id DESC
        LIMIT 1
        """,
        {"application_no": application_no},
    )
