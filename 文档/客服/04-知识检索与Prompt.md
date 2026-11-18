# 04 知识检索与 Prompt

知识检索负责回答“不是办业务，而是想了解”的问题：利率、手续费、提前还款、产品介绍、风险提示等。

## 1. 整体链路

```text
用户文本
  → TurnPlanner（turn_plan.jinja2）   产出 knowledge.intents
  → TurnPlanValidator                 校验只命中一个方向
  → KnowledgeHandler                  意图 → provider_ids → 并发取数
  → Provider（api.* / faq.* / rag.*） 返回 list[KnowledgeChunk]
  → KnowledgeResponder（knowledge_respond.jinja2）
  → BotMessage
```

要点：

- 意图 ID 只能来自 `assistant/knowledge/intents.py`；LLM 给出未登记的意图会被 `KNOWLEDGE_INTENTS.get()` 跳过，不再抛 `KeyError`。
- 多个意图的 `provider_ids` 用 `dict.fromkeys` 去重，**保留声明顺序**，即 Provider 的优先级。
- 单个 Provider 异常只返回空结果或错误说明，不影响其他 Provider。
- 请求流程的优先级高于知识检索：同一个请求既能走流程又能查知识时，走流程。

## 2. 知识意图

`assistant/knowledge/intents.py`：

| intent id | 含义 | provider_ids | 需要对象 |
| --- | --- | --- | --- |
| `account_info` | 账户、余额、冻结金额 | `api.account` | `account` |
| `transaction_info` | 交易流水、收支明细 | `api.transaction` | `transaction` |
| `card_info` | 银行卡、信用卡信息 | `api.account` | `card` |
| `loan_product_info` | 贷款产品、利率、期限 | `api.loan`、`faq.default`、`rag.default` | 否 |
| `wealth_product_info` | 理财产品 | `api.wealth`、`faq.default`、`rag.default` | 否 |
| `fund_product_info` | 基金产品 | `api.wealth`、`faq.default`、`rag.default` | 否 |
| `deposit_product_info` | 存款、账户产品 | `api.deposit`、`faq.default`、`rag.default` | 否 |
| `credit_card_info` | 信用卡年费、权益、额度 | `faq.default`、`rag.default` | 否 |
| `interest_rate` | 利率说明 | `faq.default`、`rag.default` | 否 |
| `fee_rule` | 手续费规则 | `faq.default`、`rag.default` | 否 |
| `early_repayment` | 提前还款政策 | `faq.default`、`rag.default` | 否 |
| `credit_card_repayment` | 信用卡还款规则 | `faq.default`、`rag.default` | 否 |
| `risk_disclosure` | 风险提示与合规说明 | `faq.default`、`rag.default` | 否 |
| `product_intro` | 产品介绍 | `rag.default` | 否 |
| `usage_guide` | 办理与使用指南 | `rag.default` | 否 |
| `finance_policy` | 金融政策与监管规则 | `rag.default` | 否 |
| `general_finance_info` | 通用金融信息 | `faq.default`、`rag.default` | 否 |

`requires_object` 目前只用于声明“这类问题通常需要一个业务对象”，不参与校验。实际缺对象时，`api.account` 会退化为查账户列表，`api.transaction` 会明确提示“没有定位到要查询的账户”，不会编造数据。

## 3. Provider

注册入口：`assistant/knowledge/provider.py` 的 `register_default_providers()`，在 `engine/builder.py` 里注入 `KnowledgeProviderRegistry`。

| provider_id | 数据来源 | 说明 |
| --- | --- | --- |
| `api.account` | `GET /customers/{customer_no}/accounts`<br>`GET /accounts/{account_no}` | 有聚焦账户时查详情，否则查列表 |
| `api.transaction` | `GET /accounts/{account_no}/transactions` | 默认查最近 30 天、前 20 条；没有账户号时明确提示 |
| `api.loan` | `GET /loan/products`<br>`GET /loan/products/{code}` | 取前 8 个产品并补详情（产品名只在详情里） |
| `api.wealth` | `GET /wealth/products` | 前 10 个在售产品 |
| `api.deposit` | `GET /foundation/account-products` | 前 10 个账户产品 |
| `faq.default` | 本地 `faq_items` 表 | 关键词 + 二元组重叠打分，取前 3 条 |
| `rag.default` | `FINANCE_RAG_BASE_URL` | 未配置直接返回空 |

### 3.1 Provider 扩展方式

```python
class MyProvider(KnowledgeProvider):
    provider_id = "api.xxx"

    async def fetch(self, query, state, user_message) -> list[KnowledgeChunk]:
        data = await finance_request("GET", "/xxx", customer_no=resolve_customer_no(state))
        return [KnowledgeChunk(content=json.dumps(data, ensure_ascii=False), source="我的数据源")]
```

然后在 `register_default_providers()` 的列表里加一行，并在 `intents.py` 的某个意图 `provider_ids` 中引用。

## 4. FAQ 表

表由服务启动时自动创建（`assistant/repository/orm/faq.py`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int PK | 自增 |
| `question` | varchar(255) | 标准问题 |
| `answer` | text | 标准答案 |
| `keywords` | varchar(255) | 逗号分隔关键词，命中权重 2 |
| `category` | varchar(64) | 分类，如 loan / fee / card |
| `enabled` | int | 1 启用，0 停用 |

初始化数据示例：

```sql
INSERT INTO faq_items (question, answer, keywords, category, enabled) VALUES
('贷款年利率怎么计算', '贷款年利率以合同约定为准，个人消费贷年化利率区间可在贷款产品页查看。利息按实际占用本金和天数计算。', '利率,年化,利息,怎么算', 'loan', 1),
('提前还款有违约金吗', '多数贷款产品支持提前还款。是否收取违约金、收取比例以借款合同和产品说明为准，建议在还款日前联系客服确认。', '提前还款,违约金,手续费', 'loan', 1),
('信用卡年费怎么免', '普通信用卡首年免年费，刷满规定笔数可免次年年费；高端卡年费政策以卡种权益说明为准。', '年费,信用卡,免年费', 'card', 1),
('转账手续费多少', '本行账户间转账免费；跨行转账按金额分档收费，具体以转账页面展示为准。', '转账,手续费,跨行', 'fee', 1),
('理财保本吗', '理财产品不承诺保本保收益，存在本金损失风险。请根据自身风险承受能力选择，理财有风险，投资需谨慎。', '理财,保本,风险,收益', 'wealth', 1);
```

FAQ 召回逻辑（`FaqProvider`）：

1. `keywords` 按中英文逗号、顿号拆分，词命中 +2 分；
2. 问题与用户问句的二字切片重叠，每片 +0.5 分；
3. 取分数大于 0 的前 3 条，拼成“问：… 答：…”交给 LLM 润色。

没有命中时返回空列表，最终由 LLM 依据其他 Provider 或直接说明“信息不足”。

## 5. RAG

`FINANCE_RAG_BASE_URL` 非空时，`RagProvider` 会 `POST {base}/retrieve`：

```json
{"query": "用户问题", "top_k": 3}
```

期望响应：

```json
{"data": {"chunks": [{"content": "片段", "source": "文档名"}]}}
```

超时 5 秒。未配置或调用失败时返回空，不影响 FAQ 与接口数据。

## 6. Prompt 文件

目录 `assistant/prompts/jinja2/`，由 `assistant/prompts/loader.py` 读取。

### 6.1 turn_plan.jinja2（意图识别）

输入变量：

| 变量 | 内容 |
| --- | --- |
| `user_message` | 当前用户消息 |
| `conversation_history` | 最近对话 |
| `focused_object_json` | 当前聚焦对象 |
| `flows_json` | 流程清单（不含 steps，避免幻觉） |
| `task_state_json` | 活动/暂停任务 |
| `knowledge_intents_json` | 意图清单 |
| `current_date` / `week_ago` | 当前日期、7 天前，用于解析相对时间 |

输出严格 JSON：`task` / `knowledge` / `chitchat` 三选一（极少数多意图场景可并存）。Prompt 中固化了金额、期限、日期的归一化规则，例如“借五万” → `"loan_amount": "50000"`、“两年” → `"loan_term_months": "24"`。

### 6.2 knowledge_respond.jinja2（知识回复）

输入：`knowledge_content`（Provider 拼接结果）、`history`、`user_message`。

约束：只依据给定资料、不编造产品与利率、金额千分位、风险提示、不泄露完整卡号证件号、资料不足要说明。

### 6.3 clarify_respond.jinja2（澄清改写）

输入：`reason`、`clarify_message`、`focused_object`、`history`、`user_message`。只做自然化改写，不允许新增信息。

### 6.4 chitchat_respond.jinja2（闲聊）

人设为“金融智能助手”，可说明能办理账户查询、交易查询、贷款申请、信用卡挂失、投诉工单；不提供投资建议，不索要密码和验证码。

## 7. 合规注意

- 不承诺保本、保收益；理财类回答必须带风险提示。
- 不引导用户提供密码、短信验证码、完整卡号。
- 利率、费率、额度只允许引用接口或 FAQ/知识库原文，不允许模型自行计算或推测。
- 工单内容中的卡号、证件号必须先脱敏再落库。
