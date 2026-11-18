# 金融智能客服改造总览（掌柜小二）

> 基于 `customer_service老师代码` 骨架，选择金融方向落地。
>
> **路径基准**
>
> - 客服工程：`d:\dev\workspace\customer_service老师代码`
> - 金融数据服务：`d:\dev\workspace\23_电商小二\尚硅谷大模型项目实战之掌柜小二实战\finance-data`
> - 本文档目录：`finance-data\文档`

---

## 0. 文档依据（已逐项核对源码）

本文档不是凭空设计，接口字段、枚举、错误码、流程结构都对过两边源码与种子数据：

| 来源 | 核对内容 |
|---|---|
| `atguigu\task\flow\steps.py`、`loader.py`、`flow_executor.py` | flow YAML 结构（`start/collect/action/response/end`）、`next` 条件跳转、`len(next)==1` 时条件失效的捷径 |
| `atguigu\engine\dialogue_engine.py`、`task\flowexecutor\flow_executor.py` | 对象消息 `order/product` 硬编码的确切位置 |
| `atguigu\task\action\builder.py`、`action_runner.py` | Action 只扫 `custom/` 一层、失败不捕获异常 |
| `atguigu\knowledge\*.py`、`engine\builder.py` | `KnowledgeIntent` / Provider 注册方式、`KNOWLEDGE_INTENTS[intent]` 的 KeyError 风险 |
| `finance-data\app\routers\accounts.py`、`loans.py`、`operations.py` | 接口路径、请求字段、返回字段、校验逻辑 |
| `finance-data\app\dependencies.py`、`errors.py` | 鉴权头、错误 `code` 为字符串、403/404 状态码 |
| `finance-data\app\main.py`、`Makefile`、`.env` | 启动方式 `uv run -m app.main`、端口 8000、库 `finance` |
| `finance-data\seeds\2_product\loan_product.csv` | `loan_type`、`repayment_method` 的真实英文枚举 |
| `finance-data\seeds\1_foundation\dim_channel.csv`、`dim_employee.csv` | 演示渠道 `MOBILE_BANK`、员工 `EMP000001` |
| `finance-data\generate\layers\layer2.py`、`app\utils.py` | 客户号格式 `CUS` + 8 位、编号前缀 `LAP`/`TKT`/`ACC` |

---

## 1. 项目目标

把老师代码的电商客服骨架改造成金融智能客服，覆盖两类能力：

1. **信息检索**：账户、银行卡、贷款、理财、基金、交易流水、FAQ、知识库。
2. **任务型对话**：账户查询、交易查询、贷款申请、信用卡挂失、投诉工单。

同时保留骨架已有的：

- 多轮槽位收集与上下文保持
- 流程切换 / 恢复 / 取消
- 业务对象消息自动填槽
- 会话状态持久化与恢复
- SSE 流式与非流式响应
- 闲聊兜底与意图澄清

---

## 2. 范围基线

### 必做

| 能力 | 说明 |
|---|---|
| 账户查询 | 账户号或当前客户账户列表，返回余额、可用余额、冻结金额 |
| 交易查询 | 账户号 + 时间范围，返回交易流水摘要 |
| 贷款申请 | 收集贷款类型、金额、期限、用途、还款方式，查授信额度后提交，返回申请编号 |
| 信用卡挂失 | 收集卡号、挂失原因、身份信息，创建挂失工单并返回工单号 |
| 投诉工单 | 收集工单类型、关联交易号、问题描述，创建投诉工单并返回工单号 |
| FAQ / 知识库 | 利率、手续费、提前还款、信用卡还款、风险提示、产品介绍、使用指南 |
| 对话管控 | 槽位收集、流程切换、恢复、取消、会话持久化 |

### 简化

- 贷款申请只做到 **“提交申请并返回申请编号”**，不做授信审批、合同、放款、还款全链路。
- 身份验证只做 **必填校验 + 信息脱敏**，不接真实公安/人脸核验。
- 信用卡挂失落 **客服工单**，不新增信用卡实体表。

### 不做

- 理财申购/赎回、还款、对账、风控审批、催收等后台链路。
- 新增金融数据服务的表结构，除非确认现有接口无法满足。

---

## 3. 改造地图

| 层 | 位置 | 改什么 |
|---|---|---|
| 配置 | `.env`、`atguigu/conf/config.py` | 金融 API 地址、渠道编码、操作员、演示客户 |
| HTTP | `atguigu/utils/httpx_client.py` | 统一金融鉴权头 |
| 流程 | `flow_config/user_flows.yml` | 删除电商流程，新增 7 个金融 flow 与槽位 |
| Action | `atguigu/task/action/custom/` | 新增 6 个金融 action，删除电商 action |
| 对象消息 | `atguigu/engine/dialogue_engine.py` | 增加 account/card/transaction/loan 对象映射 |
| 知识检索 | `atguigu/knowledge/intents.py`、`provider.py`、`engine/builder.py` | 金融意图、Provider、FAQ/RAG 实现 |
| Prompt | `atguigu/prompts/jinja2/` | 金融示例、话术、合规约束 |
| 会话 | `atguigu/repository/`、`atguigu/service/` | 核对状态持久化、恢复、降级 |
| 前端 | 现有聊天页面 | 金融品牌、快捷问题、业务对象快捷发送 |
| 测试 | `atguigu/test/test_eval.py` | 金融用例、流程切换/恢复/取消 |

---

## 4. 文档索引

1. [01-环境与配置](01-环境与配置.md)
2. [02-流程与槽位](02-流程与槽位.md)
3. [03-Action与对象消息](03-Action与对象消息.md)
4. [04-知识检索与Prompt](04-知识检索与Prompt.md)
5. [05-测试验收与风险](05-测试验收与风险.md)

---

## 5. 实施顺序

1. **跑通数据服务**：启动 finance-data，统一 MySQL，确认 Swagger 可访问。
2. **确定演示身份**：选一个有账户、有交易、有授信额度的客户，以及有效渠道和员工编号。
3. **配置鉴权头**：所有金融接口带 `Authorization`、`X-Channel-Code`、`X-Request-Id`。
4. **先做账户查询**：`account_query` flow + `action_query_account`，跑通第一条闭环。
5. **复制其余任务**：交易查询、贷款申请、挂失、投诉。
6. **接入知识检索**：金融意图 + FAQ + RAG + Prompt。
7. **补对象消息与会话恢复**：对象自动填槽，重启服务后恢复会话。
8. **整理测试与演示脚本**：按验收标准逐条验证。

---

## 6. 验收对照

| 验收标准 | 对应实现 | 演示动作 |
|---|---|---|
| 1. 业务咨询 | 金融意图 + Provider + FAQ/RAG | 问“稳健理财有哪些”“提前还款什么政策” |
| 2. 多轮槽位 | 5 个任务 flow + `set_slots` | 只给账户号，系统追问日期/金额/用途 |
| 3. 贷款/挂失/工单 | 3 个 flow + 4 个业务 action（含授信查询） | 各走一遍拿到申请号/工单号 |
| 4. 完整闭环 | 意图 → 流程 → action → 回复 → 状态 | 一条连续对话串起查询、办理、切换、恢复 |
| 5. 持久化恢复 | `DialogueStateRecord` + 会话恢复 | 重启服务后继续说“继续刚才的贷款申请” |

---

## 7. 最容易踩的坑

1. **鉴权头缺失**：finance-data 所有接口都要求 `Authorization: Bearer <customer_no>`，漏了直接 401。
2. **工单接口需要员工上下文**：`POST /support/tickets` 内部会查员工，必须带一个有效的 `X-Operator-No`，否则 403。
3. **贷款必须有 `limit_no`**：`POST /loan/applications` 要求授信额度编号，流程必须先查 `/credit-limits`。
4. **工单 `related_id` 是内部主键**：用户给的是交易业务号，直接传会校验失败；统一用 `related_type=none`，把交易号写进内容。
5. **没有信用卡实体**：finance-data 没有信用卡表，挂失只能落工单。
6. **Action 不能放子包**：`register_custom_action` 只扫描 `custom/` 下一层 `.py`，子包会被跳过。
7. **MySQL 密码/端口冲突**：finance-data 默认 `123321`，老师代码默认 `123456`，先统一。
8. **日期解析**：交易查询用 ISO 时间，Prompt 里要注入当前日期，避免模型猜“昨天”。
