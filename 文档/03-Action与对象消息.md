# 03 Action 与对象消息

对应文件：

- `customer_service老师代码\atguigu\task\action\custom\`
- `customer_service老师代码\atguigu\task\action\builder.py`
- `customer_service老师代码\atguigu\engine\dialogue_engine.py`
- `customer_service老师代码\atguigu\task\flowexecutor\flow_executor.py`

---

## 1. Action 注册规则（先看，避免白写）

`atguigu/task/action/builder.py` 的 `register_custom_action` 只扫描
`atguigu/task/action/custom/` **下一层的 `.py` 文件**，遇到子包直接 `continue`。

所以：

- ✅ `custom/finance_account_query.py`
- ❌ `custom/finance/account_query.py`（不会被注册）

另外，`custom/` 里原来的两个电商 action 被 `builder.py` 顶部显式 import 了：

```python
from atguigu.task.action.custom.logistics_tracking import LogisticsTrackingAction
from atguigu.task.action.custom.order_status_query import OrderStatusAction
```

删除这两个文件时，要同步删掉这两行 import，否则启动直接报 `ModuleNotFoundError`。
`register_action` 当前是注释状态，只保留了 import，所以改 import 即可。

Action 基类约定（`atguigu/task/action/base.py`）：

```python
class Action(ABC):
    name: str = ""

    @abstractmethod
    async def run(self, state: DialogueState) -> ActionResult:
        pass
```

`ActionResult` 只有一个字段：`slots_update: dict[str, Any]`。
ActionRunner **不捕获异常**，所以每个 action 必须自己 `try/except`，失败时写 `error_message` 和展示文本槽位。

---

## 2. 公共工具模块

在 `atguigu/utils/` 下新增 `finance_client.py`（公共 HTTP 工具，Action 和知识 Provider 都可以复用）。

```python
import uuid
from decimal import Decimal
from typing import Any

import httpx

from atguigu.conf.config import settings
from atguigu.domain.state import DialogueState
from atguigu.utils.httpx_client import finance_headers


def active_slots(state: DialogueState) -> dict[str, Any]:
    task = state.tasks.active
    return task.slots if task else {}


def resolve_customer_no(state: DialogueState) -> str:
    # 演示阶段固定使用配置里的客户；生产环境改成 sender_id -> customer_no 的登录映射
    return settings.demo_customer_no


async def finance_request(
    method: str,
    path: str,
    *,
    customer_no: str,
    with_operator: bool = False,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict:
    url = f"{settings.finance_api_base_url.rstrip('/')}/api/v1{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.request(
            method,
            url,
            headers=finance_headers(customer_no, with_operator=with_operator),
            params=params,
            json=json_body,
        )
    try:
        payload = resp.json()
    except Exception as exc:
        raise RuntimeError(f"金融接口返回非 JSON：HTTP {resp.status_code}") from exc

    # 成功 code=0；错误也可能以 HTTP 200 + 非 0 code 返回，两个都要判
    if resp.status_code >= 400 or payload.get("code") != 0:
        raise RuntimeError(payload.get("message") or f"金融接口错误：HTTP {resp.status_code}")
    return payload.get("data") or {}


def money(value: Any) -> str:
    return f"{Decimal(str(value or '0')):,.2f}"


def new_request_no(slots: dict) -> str:
    # 写接口幂等号：第一次生成后写回槽位，重试复用，避免重复提交
    request_no = slots.get("request_no")
    if not request_no:
        request_no = str(uuid.uuid4())
        slots["request_no"] = request_no
    return request_no


def mask_no(value: str, keep: int = 4) -> str:
    value = str(value or "")
    if len(value) <= keep:
        return value
    return "*" * (len(value) - keep) + value[-keep:]
```

> `finance_headers` 的实现见 [01-环境与配置](01-环境与配置.md)。

---

## 3. Action 清单

| 文件（直接放 `custom/`） | 类名 | `name` | 接口 | 写入槽位 |
|---|---|---|---|---|
| `finance_account_query.py` | `QueryAccountAction` | `action_query_account` | `GET /api/v1/accounts/{account_no}` 或 `GET /api/v1/customers/{customer_no}/accounts` | `account_summary`、`balance_amount`、`available_amount`、`frozen_amount` |
| `finance_transaction_query.py` | `QueryTransactionsAction` | `action_query_transactions` | `GET /api/v1/accounts/{account_no}/transactions` | `transaction_summary` |
| `finance_credit_limit.py` | `QueryCreditLimitAction` | `action_query_credit_limit` | `GET /api/v1/customers/{customer_no}/credit-limits` + `GET /api/v1/loan/products` + `GET /api/v1/loan/products/{product_code}` | `limit_no`、`product_code`、`repayment_method`、`credit_limit_summary`、`loan_result` |
| `finance_loan_submit.py` | `SubmitLoanApplicationAction` | `action_submit_loan_application` | `POST /api/v1/loan/applications` | `loan_application_no`、`loan_result` |
| `finance_card_loss.py` | `ReportCardLossAction` | `action_report_card_loss` | `POST /api/v1/support/tickets` | `ticket_no`、`loss_result` |
| `finance_complaint.py` | `CreateComplaintTicketAction` | `action_create_complaint_ticket` | `POST /api/v1/support/tickets` | `ticket_no`、`ticket_result` |

删除：

- `custom/logistics_tracking.py`
- `custom/order_status_query.py`
- `atguigu/task/action/builder.py` 顶部的对应 import

---

## 4. 各 Action 实现要点

**统一约定（适用于下面所有 action）**

- `ActionRunner` 不捕获异常，每个 `run` 都必须整体 `try/except`，始终返回 `ActionResult`。
- 失败时写 `error_message` + 对应展示槽位（`account_summary` / `transaction_summary` /
  `loan_result` / `loss_result` / `ticket_result`），不要让异常冒到引擎。
- 写接口失败时不要写 `limit_no` / `loan_application_no` / `ticket_no`，否则流程分支会误判成功。
- 金额统一用 `Decimal`，传给接口时转字符串；期限转 `int`。

### 4.1 `action_query_account`

**输入槽位**：`account_no`（可选）、`account_scope`（可选，`all`）。

**逻辑**：

1. `account_scope == "all"` 或 `account_no` 为空 → 调客户账户列表接口。
2. 否则调账户详情接口。
3. 账户详情返回只有 `account_status`、`balance_amount`、`frozen_amount`、`account_product`
   （`account_product` 里是 `product_code`、`product_name`、`account_type`、`product_status`）。
   **不返回 `account_no` 和 `currency_code`**，展示时用槽位里的账户号。
4. 账户列表返回 `data.list[]`，每项含 `account_no`、`balance_amount`、`currency_code`、
   `account_product {product_code, product_name}`；列表没有 `account_status` 和 `frozen_amount`。
5. `available_amount` 两个接口都不返回：详情按 `balance_amount - frozen_amount` 计算，
   列表只能按“可用 = 余额”展示，或提示用户查单个账户看冻结金额。
6. 写 `account_summary`，例如：

```text
账户 6222****1234（活期一本通）
余额：12,345.67 元
可用余额：12,345.67 元
冻结金额：0.00 元
状态：正常
```

多账户时逐行拼接，最多展示 10 个，其余提示“还有 N 个账户”。

**异常**：写 `account_summary = "账户查询失败，请稍后再试。"` 和 `error_message`。

---

### 4.2 `action_query_transactions`

**输入槽位**：`account_no`、`transaction_start_date`、`transaction_end_date`。

**接口**：

```text
GET /api/v1/accounts/{account_no}/transactions
    ?start_time=2026-11-01T00:00:00
    &end_time=2026-11-18T23:59:59
    &page_no=1
    &page_size=20
```

**返回**：

```json
{
  "data": {
    "list": [
      {
        "transaction_no": "TX...",
        "transaction_type": "消费",
        "transaction_status": "success",
        "transaction_amount": "128.00",
        "fee_amount": "0.00",
        "counterparty_name": "某某商户",
        "merchant_name": "某某商户",
        "transaction_at": "2026-11-17 12:30:00"
      }
    ],
    "page_no": 1,
    "page_size": 20,
    "total_count": 32
  }
}
```

**输出 `transaction_summary`**：先给总数，再列最近 10 笔，每行包含时间、类型、金额、对方、状态、交易号。
如果 `list` 为空，输出“该时间段没有交易记录”。

> 接口内部是 `SELECT * FROM account_transaction`，所以除了上面示例字段，还会带
> `id`、`customer_id`、`from_account_id`、`to_account_id`、`channel_id`、`reconcile_status`、
> `currency_code`、`related_type`、`related_id` 等，展示时只取需要的字段即可。
> `page_size` 上限是 100，超过会 422。

> 日期由 Prompt 归一化成 `yyyy-MM-dd`，action 补上 `T00:00:00` / `T23:59:59`。
> 如果用户只给了一个日期，默认结束日期为今天。

---

### 4.3 `action_query_credit_limit`

这是贷款流程的关键，做三件事：

1. **查额度**：

```text
GET /api/v1/customers/{customer_no}/credit-limits
```

返回 `data.list[]`，字段包括：

```json
{
  "limit_no": "CL...",
  "product_code": "LOAN_CONSUMER",
  "total_limit_amount": "200000.00",
  "available_limit_amount": "150000.00",
  "frozen_limit_amount": "50000.00",
  "valid_to": "2027-11-18"
}
```

2. **匹配产品**：

```text
GET /api/v1/loan/products?loan_type=consumer
```

`loan_type` 是英文枚举：`consumer` / `cash` / `installment` / `business`，
中文口语要先按 [02 的映射表](02-流程与槽位.md) 转成枚举再查。

返回 `data.list[]`，字段只有 `product_code`、`eligibility_rules`（恒为空数组）、
`rate_range {min,max}`、`term_range {min,max}`，**没有 `product_name`**。
所以要逐个查详情才能拿到产品名和 `repayment_method`；`consumer` 有 11 个产品，
最多 11 次详情调用，可以直接全查一遍，用 `product_name` 做包含匹配。

3. **查产品详情并校验**：

```text
GET /api/v1/loan/products/{product_code}
```

返回 `data.product_detail`，包含：

- `product_name`
- `loan_type`
- `min_amount` / `max_amount`
- `min_term_months` / `max_term_months`
- `repayment_method`

校验：

- `loan_amount` 在 `[min_amount, max_amount]`
- `loan_term_months` 在 `[min_term_months, max_term_months]`
- 可用额度 ≥ `loan_amount`

成功时写入（`repayment_method` 保留英文枚举，展示时转中文）：

```python
REPAYMENT_LABELS = {
    "equal_principal_interest": "等额本息",
    "equal_principal": "等额本金",
    "interest_first": "先息后本",
}

{
    "limit_no": limit["limit_no"],
    "product_code": limit["product_code"],
    "repayment_method": product_detail["repayment_method"],
    "credit_limit_summary": (
        f"可用额度 {money(available)} 元，产品 {product_detail['product_name']}，"
        f"还款方式 {REPAYMENT_LABELS.get(product_detail['repayment_method'], product_detail['repayment_method'])}"
    ),
}
```

> 额度列表接口返回该客户全部额度，且不返回 `limit_status`。
> 多条时取 `available_limit_amount` 最大的一条；额度是否可用最终由提交接口校验。

失败时**不要写 `limit_no`**，只写 `loan_result`，例如：

- “您当前没有可用授信额度，建议先申请授信。”
- “申请金额超出产品范围（1,000 ~ 200,000 元）。”
- “贷款期限超出产品范围（6 ~ 36 个月）。”

YAML 里的条件分支会根据 `slots.get('limit_no')` 决定是否继续提交。

---

### 4.4 `action_submit_loan_application`

**请求**：

```json
{
  "request_no": "<uuid>",
  "customer_no": "<DEMO_CUSTOMER_NO>",
  "limit_no": "<action_query_credit_limit 写入>",
  "apply_amount": "50000.00",
  "apply_term_months": 12,
  "repayment_method": "equal_principal_interest",
  "loan_purpose": "装修",
  "materials": []
}
```

字段来源：

| 字段 | 来源 |
|---|---|
| `request_no` | `new_request_no(slots)` |
| `customer_no` | `resolve_customer_no(state)` |
| `limit_no` | `slots["limit_no"]` |
| `apply_amount` | `slots["loan_amount"]`，转字符串 |
| `apply_term_months` | `slots["loan_term_months"]`，转 int |
| `repayment_method` | `slots["repayment_method"]` |
| `loan_purpose` | `slots["loan_purpose"]` |
| `materials` | 固定 `[]`，演示阶段不传材料 |

**返回**：

```json
{
  "data": {
    "application_no": "LAP2026111800010001",
    "application_status": "submitted"
  }
}
```

`application_no` 由 `make_no("LAP")` 生成，前缀是 `LAP`；工单号前缀是 `TKT`。

写入：

```python
{
    "loan_application_no": data["application_no"],
    "loan_result": f"贷款申请已提交，申请编号：{data['application_no']}，当前状态：已提交。",
}
```

**注意**：

- `request_no` 必须写回 `slots`，重试时复用，否则会重复提交。
- 金额用字符串或 `Decimal`，不要用 `float`。
- 接口会冻结额度，重复提交同一 `request_no` 会走幂等缓存。
- 服务端会校验：额度属于该客户、`limit_status == 'active'`、金额 ≤ 可用额度、
  金额/期限在产品区间。任一不满足直接 4xx，action 要转成用户能读懂的话术。
- `repayment_method` 虽然必填，但 `loan_application` 表没有这一列，服务端接收后不落库；
  最终还款方式以贷款产品为准，这里传产品详情里的值即可。

---

### 4.5 `action_report_card_loss`

**请求**：

```json
{
  "request_no": "<uuid>",
  "customer_no": "<DEMO_CUSTOMER_NO>",
  "ticket_type": "card_loss",
  "ticket_title": "信用卡挂失",
  "ticket_content": "卡号：**** **** **** 1234；挂失原因：卡片丢失；持卡人：张三；证件号后四位：1234",
  "related_type": "none"
}
```

**注意**：

- 必须带 `X-Operator-No`（`with_operator=True`），否则 `current_employee` 查不到员工，返回 403。
- finance-data 没有信用卡实体，`credit_card_no` 只作为工单内容，不校验是否存在。
- 身份证号只保留后四位，写日志前脱敏。
- `related_type` 用 `none`，不要传 `related_id`。

**返回**：`data.ticket_no`、`data.ticket_status`。

写入：

```python
{
    "ticket_no": data["ticket_no"],
    "loss_result": f"信用卡挂失工单已提交，工单号：{data['ticket_no']}。我们会尽快联系您核实处理。",
}
```

---

### 4.6 `action_create_complaint_ticket`

**请求**：

```json
{
  "request_no": "<uuid>",
  "customer_no": "<DEMO_CUSTOMER_NO>",
  "ticket_type": "<slots.ticket_type 或 complaint>",
  "ticket_title": "客户投诉",
  "ticket_content": "问题描述：转账一直没到账；关联交易号：TX...",
  "related_type": "none"
}
```

**注意**：

- 同样需要 `X-Operator-No`。
- `ticket_type` 建议做一层中文映射：投诉 → `complaint`，咨询 → `consult`，建议 → `suggestion`，
  避免把“投诉”直接写进库影响后台筛选。
- 交易号是可选信息，用户没给就不写“关联交易号”这一行。
- 交易号优先取 `related_transaction_no`，没有就回退到 `transaction_no`：

```python
related_no = slots.get("related_transaction_no") or slots.get("transaction_no")
```

- 不要用 `related_type=transaction` + `related_id=<交易业务号>`：接口的 `related_id` 是数据库主键，
  用户给的是业务号，校验会失败。统一 `none`，把交易号写进 `ticket_content`。

写入：

```python
{
    "ticket_no": data["ticket_no"],
    "ticket_result": f"投诉工单已提交，工单号：{data['ticket_no']}。处理进度可在工单中查看。",
}
```

---

## 5. Action 代码骨架

以账户查询为例：

```python
from atguigu.domain.state import DialogueState
from atguigu.task.action.base import Action, ActionResult

from atguigu.utils.finance_client import (
    active_slots,
    finance_request,
    money,
    resolve_customer_no,
)


class QueryAccountAction(Action):
    name = "action_query_account"

    async def run(self, state: DialogueState) -> ActionResult:
        slots = active_slots(state)
        customer_no = resolve_customer_no(state)
        account_no = str(slots.get("account_no") or "").strip()
        scope = str(slots.get("account_scope") or "").strip()

        try:
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
                "account_summary": "账户查询失败，请稍后再试。",
            })

    def _one_account(self, account_no: str, account: dict) -> dict:
        balance = account.get("balance_amount") or "0"
        frozen = account.get("frozen_amount") or "0"
        available = str(float(balance) - float(frozen))  # 生产环境用 Decimal
        product = account.get("account_product") or {}
        summary = (
            f"账户 {account_no}"
            f"（{product.get('product_name', '银行账户')}）\n"
            f"余额：{money(balance)} 元\n"
            f"可用余额：{money(available)} 元\n"
            f"冻结金额：{money(frozen)} 元\n"
            f"状态：{account.get('account_status', '-')}"
        )
        return {
            "account_summary": summary,
            "balance_amount": money(balance),
            "available_amount": money(available),
            "frozen_amount": money(frozen),
        }

    def _many_accounts(self, accounts: list[dict]) -> dict:
        lines = []
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
            "balance_amount": "",
            "available_amount": "",
            "frozen_amount": "",
        }
```

> 骨架里用 `float` 只是为了示例可读；实际请用 `Decimal`，避免金额精度问题。

---

## 6. 对象消息映射

有三个地方硬编码了 `order` / `product`，都要改：

### 6.1 `flow_executor.get_slot_data_from_object_message`

位置：`atguigu/task/flowexecutor/flow_executor.py` 约 179–201 行。

把 `order/product` 的 if 分支换成映射表：

```python
OBJECT_SLOT_MAP = {
    "account": {"account_no"},
    "card": {"card_no"},
    "credit_card": {"credit_card_no"},
    "transaction": {"transaction_no", "related_transaction_no"},
    "loan": {"loan_application_no"},
}


def get_slot_data_from_object_message(self, step, state):
    focused = state.shared.focused_object
    if not focused:
        return

    slot_names = OBJECT_SLOT_MAP.get(focused.type, set())
    if step.slot_name not in slot_names:
        return

    state.tasks.active.slots[step.slot_name] = focused.id

    # 银行卡对象可以顺带带出账户号
    if focused.type == "card" and focused.attributes.get("account_no"):
        state.tasks.active.slots["account_no"] = focused.attributes["account_no"]

    # 交易对象可以顺带带出账户号
    if focused.type == "transaction" and focused.attributes.get("account_no"):
        state.tasks.active.slots["account_no"] = focused.attributes["account_no"]
```

### 6.2 `dialogue_engine._is_can_fill_slots`

位置：`atguigu/engine/dialogue_engine.py` 约 223–233 行。

```python
OBJECT_SLOT_MAP = {...}  # 同上，抽到公共模块更好

slot_name = step.slot_name
object_type = state.shared.focused_object.type
return slot_name in OBJECT_SLOT_MAP.get(object_type, set())
```

### 6.3 `dialogue_engine._execute_object_message`

位置：约 177–188 行。现在非 `order` 一律当 `product`，要改成显式映射：

```python
obj = user_message.object
slots: dict[str, str] = {}

if obj.type == "account":
    slots["account_no"] = obj.id
elif obj.type == "card":
    slots["card_no"] = obj.id
    if obj.attributes.get("account_no"):
        slots["account_no"] = obj.attributes["account_no"]
elif obj.type == "credit_card":
    slots["credit_card_no"] = obj.id
elif obj.type == "transaction":
    slots["transaction_no"] = obj.id
    slots["related_transaction_no"] = obj.id
    if obj.attributes.get("account_no"):
        slots["account_no"] = obj.attributes["account_no"]
elif obj.type == "loan":
    slots["loan_application_no"] = obj.id
else:
    return await self.clarify_response.response(
        reason=ClarifyReason.OBJECT_REQUIRES_INTENT,
        state=state,
        user_message=user_message,
    )

command = SetSlotsCommand(command="set_slots", slots=slots)
```

这样前端发送账户、银行卡、交易、贷款对象时，就能自动填槽，不需要用户再打字。

---

## 7. 清理清单

- [ ] 删除 `custom/logistics_tracking.py`
- [ ] 删除 `custom/order_status_query.py`
- [ ] 删除 `atguigu/task/action/builder.py` 第 13–14 行 import
- [ ] 新增 6 个金融 action + `atguigu/utils/finance_client.py`
- [ ] 修改 `flow_executor.py` 对象映射
- [ ] 修改 `dialogue_engine.py` 对象判断与填槽
- [ ] 启动后日志确认 6 个 action 都已注册
- [ ] 用对象消息分别测试 account / credit_card / transaction
