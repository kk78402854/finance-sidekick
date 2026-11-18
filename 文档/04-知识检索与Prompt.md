# 04 知识检索与 Prompt

对应文件：

- `customer_service老师代码\atguigu\knowledge\intents.py`
- `customer_service老师代码\atguigu\knowledge\provider.py`
- `customer_service老师代码\atguigu\knowledge\knowledge_handler.py`
- `customer_service老师代码\atguigu\engine\builder.py`
- `customer_service老师代码\atguigu\prompts\jinja2\`

---

## 1. 意图配置

用下面的内容替换 `KNOWLEDGE_INTENTS`：

```python
KNOWLEDGE_INTENTS: dict[str, KnowledgeIntent] = {
    # ---------- 需要业务对象的意图 ----------
    "account_info": KnowledgeIntent(
        id="account_info",
        description="账户、余额、可用余额、冻结金额咨询",
        provider_ids=["api.account"],
        requires_object="account",
    ),
    "transaction_info": KnowledgeIntent(
        id="transaction_info",
        description="交易流水、消费记录、收支明细咨询",
        provider_ids=["api.transaction"],
        requires_object="transaction",
    ),
    "card_info": KnowledgeIntent(
        id="card_info",
        description="银行卡信息咨询",
        provider_ids=["api.account"],
        requires_object="card",
    ),

    # ---------- 产品咨询 ----------
    "loan_product_info": KnowledgeIntent(
        id="loan_product_info", description="贷款产品咨询",
        provider_ids=["api.loan", "faq.default", "rag.default"],
    ),
    "wealth_product_info": KnowledgeIntent(
        id="wealth_product_info", description="理财产品咨询",
        provider_ids=["api.wealth", "faq.default", "rag.default"],
    ),
    "fund_product_info": KnowledgeIntent(
        id="fund_product_info", description="基金产品咨询",
        provider_ids=["api.wealth", "faq.default", "rag.default"],
    ),
    "deposit_product_info": KnowledgeIntent(
        id="deposit_product_info", description="存款产品咨询",
        provider_ids=["api.deposit", "faq.default", "rag.default"],
    ),
    "credit_card_info": KnowledgeIntent(
        id="credit_card_info", description="信用卡年费、权益、额度咨询",
        provider_ids=["faq.default", "rag.default"],
    ),

    # ---------- FAQ / 知识库 ----------
    "interest_rate": KnowledgeIntent(
        id="interest_rate", description="利率说明",
        provider_ids=["faq.default", "rag.default"],
    ),
    "fee_rule": KnowledgeIntent(
        id="fee_rule", description="手续费规则",
        provider_ids=["faq.default", "rag.default"],
    ),
    "early_repayment": KnowledgeIntent(
        id="early_repayment", description="提前还款政策",
        provider_ids=["faq.default", "rag.default"],
    ),
    "credit_card_repayment": KnowledgeIntent(
        id="credit_card_repayment", description="信用卡还款规则",
        provider_ids=["faq.default", "rag.default"],
    ),
    "risk_disclosure": KnowledgeIntent(
        id="risk_disclosure", description="风险提示与合规说明",
        provider_ids=["faq.default", "rag.default"],
    ),
    "product_intro": KnowledgeIntent(
        id="product_intro", description="金融产品介绍",
        provider_ids=["rag.default"],
    ),
    "usage_guide": KnowledgeIntent(
        id="usage_guide", description="业务办理和使用指南",
        provider_ids=["rag.default"],
    ),
    "finance_policy": KnowledgeIntent(
        id="finance_policy", description="金融政策和监管规则",
        provider_ids=["rag.default"],
    ),
    "general_finance_info": KnowledgeIntent(
        id="general_finance_info", description="通用金融信息咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
}
```

注意：

- `requires_object` 的值必须与对象消息的 `type` 一致（`account`、`card`、`transaction` 等）。
- `provider_ids` 里写的 id 必须在 Provider 注册表里存在，否则运行时报 `KeyError`。

---

## 2. Provider 改造

### 2.1 Provider 清单

| provider_id | 类名 | 数据来源 |
|---|---|---|
| `api.account` | `ApiAccountProvider` | `GET /customers/{customer_no}/accounts` 或 `GET /accounts/{account_no}` |
| `api.transaction` | `ApiTransactionProvider` | `GET /accounts/{account_no}/transactions` |
| `api.loan` | `ApiLoanProvider` | `GET /loan/products`（`loan_type` 用枚举 `consumer/cash/installment/business`） |
| `api.wealth` | `ApiWealthProvider` | `GET /wealth/products`（可按 `product_type` 过滤基金/理财） |
| `api.deposit` | `ApiDepositProvider` | `GET /foundation/account-products` |
| `faq.default` | `FAQProvider` | `customer_service` 库的 `faq_items` 表 |
| `rag.default` | `RAGProvider` | finance-brain 查询接口或 Milvus |

### 2.2 业务 Provider 示例

> 统一从 `atguigu.utils.finance_client` 导入 `finance_request`、`active_slots`、`money`，
> 和 Action 层复用同一套鉴权与错误处理。

```python
class ApiAccountProvider(KnowledgeProvider):
    provider_id = "api.account"

    async def execute(self, state: DialogueState,
                      user_message: UserMessage) -> list[KnowledgeChunk]:
        customer_no = settings.demo_customer_no
        account_no = None
        if state.shared.focused_object and state.shared.focused_object.type == "account":
            account_no = state.shared.focused_object.id

        path = (
            f"/accounts/{account_no}"
            if account_no
            else f"/customers/{customer_no}/accounts"
        )
        data = await finance_request("GET", path, customer_no=customer_no)
        return [KnowledgeChunk(content=json.dumps(data, ensure_ascii=False))]
```

其他 Provider 同理，只换路径和参数：

- `ApiTransactionProvider`：从 `focused_object` 取 `transaction_no` 或 `account_no`；
  如果只有交易号，先查账户流水再筛选，或者在 Prompt 里要求用户提供账户号。
- `ApiLoanProvider`：`/loan/products`，`loan_type` 传英文枚举；列表不返回 `product_name`，
  需要产品名时再查 `/loan/products/{product_code}` 取 `product_detail`。
- `ApiWealthProvider`：`/wealth/products`，返回产品列表后按 `product_type` 过滤。
- `ApiDepositProvider`：`/foundation/account-products`。

> finance-data 没有独立的信用卡实体，`credit_card_info` 走 FAQ/RAG，不要写 `ApiCreditCardProvider`。

### 2.3 FAQ Provider

先建表：

```sql
CREATE TABLE IF NOT EXISTS faq_items (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    question VARCHAR(255) NOT NULL,
    answer TEXT NOT NULL,
    keywords VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'general',
    enabled TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

示例数据（至少准备 20 条）：

| question | answer | keywords |
|---|---|---|
| 提前还款有违约金吗 | 提前还款是否收取违约金取决于贷款产品合同，请在贷款详情页查看“提前还款规则”，或转人工核实。 | 提前还款,违约金,手续费 |
| 贷款利率是多少 | 贷款利率以申请时产品详情页展示为准，不同产品、期限和客户风险等级会有差异。 | 利率,利息,年化 |
| 信用卡挂失后多久生效 | 挂失工单提交后立即冻结卡片，新卡一般 3–7 个工作日寄出。 | 挂失,生效,补卡 |
| 转账手续费怎么收 | 行内转账免费，跨行转账按金额分档收费，具体以转账页面提示为准。 | 手续费,转账,跨行 |
| 贷款申请需要什么材料 | 通常需要身份证、收入证明和用途证明，具体以产品详情页的“所需材料”为准。 | 贷款,材料,申请 |
| 理财产品有风险吗 | 理财非存款，产品有风险，投资须谨慎，过往业绩不代表未来收益。 | 风险,理财,收益 |
| 信用卡最低还款怎么算 | 最低还款额通常为账单金额的 10%，具体以账单展示为准。 | 最低还款,信用卡,账单 |
| 交易限额是多少 | 不同渠道和账户类型的限额不同，请以转账页面提示或账户详情为准。 | 限额,交易,转账 |

`FAQProvider` 用关键词命中数排序即可，不引入额外依赖：

> `fetch_faq_rows()` 用 `atguigu/utils/db.py` 的异步会话查询 `faq_items`，
> 返回 `list[dict]` 即可；不要在 Provider 里拼接 SQL 字符串。

```python
class FAQProvider(KnowledgeProvider):
    provider_id = "faq.default"

    async def execute(self, state: DialogueState,
                      user_message: UserMessage) -> list[KnowledgeChunk]:
        text = user_message.text or ""
        if not text.strip():
            return []

        rows = await fetch_faq_rows()  # 从 faq_items 查 enabled=1
        scored = []
        for row in rows:
            keywords = [k.strip() for k in row["keywords"].split(",") if k.strip()]
            score = sum(1 for k in keywords if k in text)
            if score:
                scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            KnowledgeChunk(content=f"问：{row['question']}\n答：{row['answer']}")
            for _, row in scored[:3]
        ]
```

### 2.4 RAG Provider

优先接 finance-brain 的查询接口。在 `.env` 增加：

```text
FINANCE_RAG_BASE_URL=http://127.0.0.1:8001
```

实现：

```python
class RAGProvider(KnowledgeProvider):
    provider_id = "rag.default"

    async def execute(self, state: DialogueState,
                      user_message: UserMessage) -> list[KnowledgeChunk]:
        text = user_message.text or ""
        if not text.strip():
            return []

        response = await httpx_client.http_client.post(
            f"{settings.finance_rag_base_url}/api/query",
            json={"query": text, "top_k": 5},
            timeout=15.0,
        )
        data = response.json()
        chunks = data.get("chunks") or data.get("documents") or []
        return [
            KnowledgeChunk(content=item.get("content", ""))
            for item in chunks
            if item.get("content")
        ]
```

如果 finance-brain 没有现成的 HTTP 接口：

- 方案 A：把 finance-brain 的检索模块包一层 FastAPI，暴露 `/api/query`；
- 方案 B：复用 finance-brain 的 Milvus collection，在客服工程里直接检索；
- 方案 C：先用 FAQ 表兜底，RAG 作为后续增强。

> RAG 调用必须加超时和异常捕获，失败时返回空列表，让 FAQ 或转人工兜底，不能让整轮对话 500。

---

## 3. 注册 Provider

`atguigu/engine/builder.py` 当前只注册了 4 个：

```python
from atguigu.knowledge.provider import (
    ApiProductProvider, ApiOrderProvider, FAQProvider, RAGProvider
)

knowledge_registry = KnowledgeProviderRegistry(
    provider_objects=[
        ApiProductProvider(),
        ApiOrderProvider(),
        FAQProvider(),
        RAGProvider()
    ]
)
```

改成：

```python
from atguigu.knowledge.provider import (
    ApiAccountProvider,
    ApiTransactionProvider,
    ApiLoanProvider,
    ApiWealthProvider,
    ApiDepositProvider,
    FAQProvider,
    RAGProvider,
)

knowledge_registry = KnowledgeProviderRegistry(
    provider_objects=[
        ApiAccountProvider(),
        ApiTransactionProvider(),
        ApiLoanProvider(),
        ApiWealthProvider(),
        ApiDepositProvider(),
        FAQProvider(),
        RAGProvider(),
    ]
)
```

删除 `ApiProductProvider` / `ApiOrderProvider` 的 import。

---

## 4. KnowledgeHandler 可靠性补丁

当前 `handle` 里任何一个 Provider 抛异常，整轮对话都会失败。建议改成：

```python
final_result: list[KnowledgeChunk] = []
for provider_id in provider_ids:
    try:
        provider_obj = self.knowledge_registry.get_provider(provider_id)
        result = await provider_obj.execute(state=state, user_message=user_message)
        final_result.extend(result)
    except Exception:
        logger.exception("knowledge provider failed: %s", provider_id)
        continue
```

同时把 `get_provider_ids` 的：

```python
return list(set(final_provider_ids))
```

改成：

```python
return list(dict.fromkeys(final_provider_ids))
```

保留 `api.* → faq.default → rag.default` 的顺序，回答时 API 事实优先、FAQ 次之、RAG 兜底。

---

## 5. Prompt 改造

### 5.1 `turn_plan.jinja2`

结构不用动，`flows_json` 和 `knowledge_intents_json` 是动态注入的。需要改的是：

1. **示例**：把“订单/商品/退款”示例换成金融示例。
2. **当前日期**：在 `TurnPlanner.plan` 的 `chain.ainvoke` 入参里增加：

```python
from datetime import date

result = await chain.ainvoke(input={
    ...,
    "current_date": date.today().isoformat(),
})
```

然后在 Prompt 里加：

```text
当前日期：{{ current_date }}
用户说“昨天/最近一周/上个月”时，先把日期归一化成 yyyy-MM-dd 再写入槽位。
```

3. **路由规则**建议写成：

```text
- 查余额/账户 → start_flow account_query
- 查全部账户 → set_slots {"account_scope":"all"} + start_flow account_query
- 查流水/消费记录 → start_flow transaction_query，日期归一化为 yyyy-MM-dd
- 贷款/借钱 → start_flow loan_application
- 信用卡丢了/被盗刷 → start_flow card_loss
- 投诉/工单/建议 → start_flow complaint_ticket
- 利率/手续费/提前还款/信用卡还款/风险 → knowledge_intents
- 继续刚才的… → resume_task
- 取消/算了/不办了 → cancel_task
- 转人工 → start_flow human_handoff
```

4. **对象消息**：说明 `focused_object` 可能是 account/card/credit_card/transaction/loan，
   如果当前在收集对应槽位，可以直接填。

### 5.2 `knowledge_respond.jinja2`

增加金融合规约束：

```text
你是金融智能助手，只能基于【检索内容】回答。
禁止编造利率、费率、额度、期限、审批结果。
金额、利率必须带单位；不确定时回答“暂时没有查到，建议转人工核实”。
涉及理财/基金时，必须提示“理财非存款，产品有风险，投资须谨慎”。
不得承诺贷款一定获批。
```

### 5.3 `chitchat_respond.jinja2`

改成金融助手人设，例如：

```text
你是金融智能助手，可以帮用户查账户、查交易、申请贷款、办理挂失、提交投诉工单。
闲聊时简短回应，并引导用户回到上述业务。
```

### 5.4 `clarify_respond.jinja2`

把电商示例换成金融示例：

- “您是想查账户、查交易，还是办理贷款/挂失/投诉？”
- 对象消息缺少意图时：“请告诉我您想对这个账户/这笔交易做什么。”

---

## 6. 知识检索验收用例

| 用户输入 | 期望意图 | 期望来源 |
|---|---|---|
| 提前还款有违约金吗 | `early_repayment` | FAQ / RAG |
| 现在贷款利率多少 | `interest_rate` | FAQ / RAG |
| 信用卡挂失多久生效 | `credit_card_info` 或 `early_repayment` 邻近意图 | FAQ / RAG |
| 理财有风险吗 | `risk_disclosure` | FAQ / RAG |
| 这个账户余额多少 | `account_info` | `api.account` |
| 这笔交易为什么失败 | `transaction_info` | `api.transaction` |
| 消费贷利率多少 | `loan_product_info` | `api.loan` + FAQ/RAG |
| 有哪些稳健理财 | `wealth_product_info` | `api.wealth` + FAQ/RAG |

检查点：

- [ ] 意图能正确命中
- [ ] Provider 返回的内容进入最终 Prompt
- [ ] 检索为空时走转人工/兜底，不胡编
- [ ] 单个 Provider 超时不影响整轮回答
