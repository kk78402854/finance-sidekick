# 金融小二 · 文档总览

面向零售银行的**金融业务中台 + 智能对话客服 + 业务门户**一体化演示项目。

- 中台 `app/`：FastAPI 模拟银行核心链路（客户、账户、交易、理财、信贷、还款、风控、催收、运营 9 大域），接口前缀 `/api/v1`，端口 **8000**。
- 客服 `finance-assistant/`：把中台接口包装成流程化自然语言服务，包名 `assistant`，端口 **18083**。
- 门户 `finance-assistant/web/`：12 个零构建静态页面，客户 / 管理员 / AI 三种视角。

全部业务数据由 `generate/` 脚本生成，可一键初始化、可重复演练。

---

## 1. 系统架构

```text
┌──────────────────────────────┐        ┌──────────────────────────────────┐
│  业务门户（12 个静态页面）      │        │   AI 对话客服（/api/chat）          │
│  customer / admin / chat      │        │   引擎 + 流程 + Action + 知识库     │
└──────────────┬───────────────┘        └───────────────┬──────────────────┘
               │  /api/portal/*（BFF）                   │  Bearer 客户号 / 员工号
               ▼                                         ▼
        ┌──────────────────────────────────────────────────────┐
        │            金融中台 finance-data（FastAPI）             │
        │  客户 · 账户 · 交易 · 理财 · 信贷 · 还款 · 风控 · 催收    │
        └──────────────────────────┬───────────────────────────┘
                                   ▼
                        ┌────────────────────┐
                        │      MySQL 8.0     │
                        │ finance /          │
                        │ finance_assistant  │
                        └────────────────────┘
```

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| 业务门户 + 客服 | `18083` | 网页入口 `http://127.0.0.1:18083/` |
| 金融中台 | `8000` | 业务接口，Swagger `/docs` |
| MySQL | `3307`（Docker）/ `3306`（本地） | 映射到容器内 `3306`，避开宿主机已有实例 |

---

## 2. 三种对话能力

客服链路：`用户消息 → LLM 意图识别 → 结果校验 → 任务流程 / 知识检索 / 闲聊 → 金融接口 → LLM 润色 → 回复`。

| 能力 | 例子 | 一句话概括 |
| --- | --- | --- |
| 任务流程 task | “我要查余额” / “我要申请贷款” | 按 YAML 预定义步骤收集信息、执行 Action |
| 信息检索 knowledge | “消费贷利率是多少” | 先查可信资料（中台 API / FAQ / 知识库），再让 LLM 组织回答 |
| 闲聊 chitchat | “你好呀” | 既不是任务也不是检索，LLM 结合历史兜底 |

---

## 3. 能力清单

| 能力 | 用户说法示例 | 入口 |
| --- | --- | --- |
| 账户查询 | 查一下我的余额 / 查我全部账户 | Flow `account_query` |
| 交易查询 | 查最近一周的流水 | Flow `transaction_query` |
| 贷款申请 | 我想借五万消费贷，24 个月 | Flow `loan_application` |
| 信用卡挂失 | 我的信用卡丢了，帮我挂失 | Flow `card_loss` |
| 投诉工单 | 我要投诉重复扣款 | Flow `complaint_ticket` |
| 转人工 | 转人工 | Flow `human_handoff` |
| 产品与规则咨询 | 消费贷利率多少 / 提前还款怎么算 | 知识检索 |
| 闲聊 | 你好 / 你是谁 | 闲聊 |

同时具备：多轮槽位收集、流程切换 / 恢复 / 取消、业务对象消息自动填槽、会话状态持久化与恢复、意图澄清兜底。

---

## 4. 目录结构

```text
finance-data/
├── app/                     # 金融中台 FastAPI 服务（routers / 鉴权 / 幂等 / 响应体）
├── generate/                # 分层测试数据生成器（9 层）
├── seeds/                   # 维度与产品种子数据（CSV）
├── sql/finance.sql          # 建表脚本
├── tests/                   # 接口链路与路由覆盖测试
├── 文档/                     # 本目录：总览 + 01~06 + 全流程和全类图
├── docker/                  # docker-compose.yaml / docker-compose.full.yaml
├── init_db.py               # 建库建表
└── finance-assistant/       # 智能客服 + 业务门户
    ├── main.py              # 启动入口：初始化对话引擎并拉起 FastAPI
    ├── flow_config/         # user_flows.yml：槽位定义 + 7 个业务流程
    ├── web/                 # 12 个页面 + app.css / api.js / nav.js
    └── assistant/
        ├── api/             # 对外接口 /api/chat、/api/chat/history、/api/portal/*
        ├── engine/          # 总装工厂 builder、对话引擎 dialogue_engine
        ├── plan/            # LLM 意图识别 turn_planner、结果校验 validator
        ├── task/            # flow 流程模型 / flowexecutor / action / response / command / tasklifecycle
        ├── knowledge/       # 知识意图、Provider、检索入口、LLM 润色
        ├── clarify/         # 意图不清时的澄清
        ├── chitchat/        # 闲聊
        ├── prompts/jinja2/  # 四个提示词模板
        ├── repository/      # 会话状态持久化、FAQ 查询
        ├── domain/          # 消息、状态、对象消息到槽位的映射
        ├── service/         # 对话服务编排
        ├── conf/config.py   # pydantic-settings 读取 .env
        └── utils/           # 数据库、HTTP、金融接口客户端、LLM
```

---

## 5. 快速开始

### 方式一：Docker 一键全栈（推荐）

```bash
# 1. 首次初始化数据库并生成业务数据（会重建 finance 库）
docker compose -f docker/docker-compose.full.yaml --profile init run --rm finance-data-init

# 2. 构建并启动 mysql + 中台 + 客服
docker compose -f docker/docker-compose.full.yaml up -d --build
```

### 方式二：本地开发

```bash
# 中台
uv sync
uv run init_db.py
uv run -m generate.main --profile full
uv run -m app.main                       # http://127.0.0.1:8000

# 客服 + 门户（另开终端）
cd finance-assistant
uv sync
python main.py                           # http://127.0.0.1:18083
```

详细步骤见 [01-环境与启动.md](01-环境与启动.md)，容器化部署见 [06-Docker部署与启动.md](06-Docker部署与启动.md)。

---

## 6. 演示身份

| 视角 | 身份 | 说明 |
| --- | --- | --- |
| 客户 | `CUS00000001` | 门户右上角可切换任意客户号；作为 `Authorization: Bearer <customer_no>` |
| 管理员 | `EMP000001` | 审批、工单处理需带操作员编号 `X-Operator-No` |

渠道编码 `MOBILE_BANK` 作为 `X-Channel-Code`。三者都必须换成当前库里真实存在且启用的值，查询 SQL 见 [01-环境与启动.md](01-环境与启动.md) 第 5 节。

---

## 7. 一次完整的贷款闭环

1. 客户在「授信与贷款」选择产品与金额提交申请 → 中台冻结对应授信额度
2. 管理员在「贷款审批」通过 → 中台生成合同
3. 门户自动补齐合同文件记录 → 签约 → 全额放款
4. 放款后冻结额度转为已用额度，合同状态变为 `active`，冻结金额归零

审批动作若自动签约或放款失败，审批结果仍然保留，并在提示中给出失败原因。

---

## 8. 文档索引

| 文档 | 内容 |
| --- | --- |
| [01-环境与启动.md](01-环境与启动.md) | 运行环境、MySQL、`.env` 全量说明、演示身份、启动顺序、接口示例、错误码对照 |
| [02-流程与槽位.md](02-流程与槽位.md) | `user_flows.yml` 写法、步骤类型、条件跳转、槽位清单、7 条流程明细 |
| [03-Action与对象消息.md](03-Action与对象消息.md) | Action 注册机制、6 个 Action、公共金融客户端、对象消息填槽 |
| [04-知识检索与Prompt.md](04-知识检索与Prompt.md) | 知识意图、Provider、FAQ 表、RAG、四个 Prompt、合规约束 |
| [05-测试验收.md](05-测试验收.md) | 启动自检、验收用例、联调脚本、异常排查、风险清单、DoD |
| [06-Docker部署与启动.md](06-Docker部署与启动.md) | Compose 编排、初始化数据、启动验证、排障、重置 |
| [全流程和全类图/金融小二-整体流程详解.md](全流程和全类图/金融小二-整体流程详解.md) | 一条消息走完全流程的 ①～⑩ 环节层层放大 |
| [全流程和全类图/金融小二-模型类图详解.md](全流程和全类图/金融小二-模型类图详解.md) | 按流程顺序展示所有模型类与字段 |

---

## 9. 说明

- 全部数据由 `generate/` 脚本随机生成，客户、账户、合同、流水均不对应真实机构或个人。
- 项目中不含任何真实密钥；运行前请自行配置 `.env`，并确保不将其提交到公开仓库。
- 门户的管理端身份校验为演示级实现（客户号即身份），生产环境应替换为登录态与 RBAC。
