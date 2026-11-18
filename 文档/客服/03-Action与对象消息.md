# 03 Action 与对象消息

## 1. Action 机制

Action 是流程里唯一允许产生副作用或访问外部系统的地方。定义在 `assistant/task/action/custom/`，一个文件一个业务动作。

### 1.1 基类与返回值

```python
class Action(ABC):
    name: str = ""                                  # YAML 里的 action 名
    @abstractmethod
    async def run(self, state: DialogueState) -> ActionResult: ...
```

`ActionResult.slots_update` 是字典，执行器会把它 `update` 进当前任务的 `slots`：

```python
return ActionResult(slots_update={
    "account_summary": "账户 ... 余额 ...",
    "balance_amount": "12,345.60",
})
```

### 1.2 注册方式

`assistant/task/action/builder.py` 的 `register_custom_action` 会：

1. `importlib.import_module("assistant.task.action.custom")`；
2. `pkgutil.iter_modules` 扫描这一层，跳过子包；
3. 反射拿到每个模块里的类，只保留“Action 子类且定义在本模块”的类；
4. 无参实例化后按 `name` 注册进 `ActionRegistry.actions`。

因此新增 Action 只要放文件、写 `name`，不用改任何注册代码。

### 1.3 运行方式

`FlowExecutor` 遇到 `action` 步骤：

1. 取 YAML 的 `action` 字段构造 `ActionCall`；
2. `ActionRunner.run()` 从注册表取实例并 `await action.run(state)`；
3. 结果合并进槽位，推进下一步。

`action_runner` 本身不捕获异常，**Action 必须自己兜底**，否则整个 `/api/chat` 会 500。

## 2. 六个 Action

| Action `name` | 文件 | 接口 | 主要写入槽位 |
| --- | --- | --- | --- |
| `action_query_account` | `finance_account_query.py` | `GET /accounts/{account_no}`<br>`GET /customers/{customer_no}/accounts` | `account_summary`、`balance_amount`、`available_amount`、`frozen_amount` |
| `action_query_transactions` | `finance_transaction_query.py` | `GET /accounts/{account_no}/transactions` | `transaction_summary` |
| `action_query_credit_limit` | `finance_credit_limit.py` | `GET /customers/{customer_no}/credit-limits`<br>`GET /loan/products/{product_code}` | `limit_no`、`product_code`、`repayment_method`、`credit_limit_summary`；失败写 `loan_result` |
| `action_submit_loan_application` | `finance_loan_submit.py` | `POST /loan/applications` | `loan_application_no`、`loan_result` |
| `action_report_card_loss` | `finance_card_loss.py` | `POST /support/tickets`（`ticket_type=card_loss`） | `ticket_no`、`loss_result` |
| `action_create_complaint_ticket` | `finance_complaint.py` | `POST /support/tickets` | `ticket_no`、`ticket_result` |

### 2.1 账户查询

- 有 `account_no` 且不是“全部账户” → 查单账户详情，返回余额、可用余额、冻结金额、状态。
- 否则查 `customers/{customer_no}/accounts`，展示前 10 个账户。
- 单账户接口不返回账户号，展示时用请求里的 `account_no` 补上。
- 列表接口不返回冻结金额，此时清空 `frozen_amount`，避免和上一次查询串数据。

### 2.2 交易查询

- 缺少 `account_no` 直接返回“需要账户号”，不调用接口。
- `page_size=20`（接口上限 100），展示前 10 条。
- `start_time`/`end_time` 拼成 `yyyy-MM-ddT00:00:00` / `T23:59:59`。
- 交易类型映射：`transfer` 转账、`consume` 消费、`deposit` 存款、`withdraw` 取现、`refund` 退款、`adjustment` 调账、`wealth_income` 理财收益、`loan_disbursement` 贷款放款、`loan_repayment` 贷款还款。

### 2.3 授信额度与产品匹配

1. 取授信额度列表，**可用额度最大**的一条；
2. 用该额度的 `product_code` 查产品详情（列表接口没有产品名，不能靠猜）；
3. 校验：金额 > 0、金额 ≤ 可用额度、金额在产品 `[min_amount, max_amount]`、期限在 `[min_term_months, max_term_months]`；
4. 用户口语类型（消费贷/经营贷/现金贷/分期贷）映射为 `consumer/business/cash/installment`，与产品 `loan_type` 不一致时拒绝，避免用消费额度办经营贷；
5. 全部通过才写 `limit_no`、`repayment_method`、`product_code`，YAML 的条件分支据此进入提交步骤。

### 2.4 贷款提交

请求体：

```json
{
  "request_no": "uuid",
  "customer_no": "CUS00000001",
  "limit_no": "CL2026...",
  "apply_amount": "50000",
  "apply_term_months": 24,
  "repayment_method": "equal_principal_interest",
  "loan_purpose": "装修",
  "materials": []
}
```

- `request_no` 由 `new_request_no(slots)` 首次生成后写回槽位，用户重试时复用，接口幂等不会重复建单。
- 成功后展示 `application_no`（LAP 前缀）和 `application_status`。

### 2.5 挂失与投诉工单

- 两个工单接口都要 `with_operator=True`，即额外发送 `X-Operator-No`。
- `related_type` 固定 `none`；交易号写入 `ticket_content`，不要塞 `related_id`。
- 卡号、证件号用 `mask_no` 脱敏后再落工单内容。
- `ticket_type` 会把“投诉/咨询/建议/表扬”映射成 `complaint/consult/suggestion/praise`。

### 2.6 统一约定

| 约定 | 说明 |
| --- | --- |
| 异常兜底 | 每个 Action 用 `try/except Exception`，把中文原因写入 `error_message` 和对应的 `*_result` |
| 金额 | `to_decimal()` 解析，`money()` 展示为 `12,345.60` |
| 日期 | `normalize_date()` 兼容 `2026/11/01`、`2026.11.01`、`20261101` |
| 鉴权 | 统一走 `assistant/utils/finance_client.py`，不手写 header |
| 失败不中断 | Action 失败也返回 `ActionResult`，让流程继续到 `response` 步骤把原因告诉用户 |

## 3. 对象消息

前端可以把业务对象直接发给客服，而不是让用户复制单号。对象消息不经过 LLM，直接映射成槽位。

### 3.1 消息格式

```json
{
  "type": "account",
  "id": "6222020200000001",
  "title": "储蓄卡",
  "attributes": {"account_no": "6222020200000001"}
}
```

### 3.2 类型映射表

映射代码在 `assistant/domain/object_slots.py`。

| `type` | `id` 含义 | 可填槽位 | 额外规则 |
| --- | --- | --- | --- |
| `account` | 账户号 | `account_no` | — |
| `card` | 银行卡号 | `card_no`、`account_no` | `account_no` 取 `attributes.account_no` |
| `credit_card` | 信用卡号 | `credit_card_no` | — |
| `transaction` | 交易号 | `transaction_no`、`related_transaction_no`、`account_no` | 账户号取 `attributes.account_no` |
| `loan` | 贷款申请号 | `loan_application_no` | — |

### 3.3 处理流程

`DialogueEngine._execute_object_message`：

1. 把对象写入 `state.shared.focused_object`；
2. 若当前没有活动任务，或当前不是 `collect` 步骤，或槽位不匹配 → 走澄清回复；
3. 匹配成功 → 生成 `SetSlotsCommand` 交给 `TaskHandler`，从当前步骤继续推进。

`FlowExecutor._get_collect_data` 在槽位为空时也会读取 `focused_object`，因此“先发起流程，再点卡片”同样能填槽。

### 3.4 典型交互

用户先点账户卡片，再说“查最近一周流水”：

1. 对象消息先到，但没有活动任务 → 澄清“我已经收到这个账户了……”；
2. 用户说“查流水”，LLM 识别 `transaction_query`；
3. `start` 步骤只做跳转，不看槽位，进入 `ask_account_no`；
4. `collect` 发现槽位为空，自动从 `focused_object` 取 `account_no`，这一步不会被追问；
5. 继续追问开始日期、结束日期。

聚焦对象会一直保留到下一次对象消息或任务清空，所以“先点卡片、后办业务”是可用路径。

如果要“点卡片直接开始某个流程”，需要前端再发一条文本请求触发 `start_flow`，或者由前端在点击卡片时自行拼一条文本消息。单发对象消息不会启动流程。
