# 金融小二 · Finance Sidekick

[![CI](https://github.com/kk78402854/finance-sidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/kk78402854/finance-sidekick/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/tests-58%20passed-brightgreen)

面向零售银行的**金融业务中台 + 智能对话客服 + 业务门户**一体化演示项目。

中台用 FastAPI + MySQL 模拟真实银行核心链路（开户、账户、交易、授信、贷款、还款、风控、催收、工单），
客服侧把同一批接口封装成流程化的自然语言服务，门户则提供客户、管理员、AI 三种使用视角。
全部业务数据为程序生成的测试数据，可一键初始化、可重复演练。

---

## 界面预览

### 门户首页

![门户首页](docs/screenshots/01-home.png)

### 数据大盘（管理员）

![数据大盘](docs/screenshots/02-dashboard.png)

### 客户账户

![客户账户](docs/screenshots/03-accounts.png)

### 授信与贷款

![授信与贷款](docs/screenshots/04-credit-loans.png)

### 贷款审批（审批通过后自动签约并放款）

![贷款审批](docs/screenshots/06-approvals.png)

### AI 对话助手

![AI 对话助手](docs/screenshots/05-chat.png)

---

## 核心能力

### 1. 金融业务中台 `app/`

- 覆盖 9 大业务域：客户、账户、交易、理财、信贷、还款、风控、催收、运营
- 统一响应体、字符串错误码、幂等 `request_no`、`Bearer` 身份鉴权 + `X-Operator-No` 操作员
- 完整贷款链路：申请冻结额度 → 审批生成合同 → 签约 → 放款将冻结额度转为已用额度
- Swagger 文档：`http://127.0.0.1:8000/docs`

### 2. 智能对话客服 `finance-assistant/`

- 自研对话引擎：意图识别 → 轮次规划 → 流程执行（YAML 配置）→ 槽位校验 → Action 调用 → 对象消息渲染
- 6 个金融 Action：账户查询、交易查询、贷款申请、授信查询、卡片挂失、投诉工单
- 知识问答：20 条 FAQ 种子数据（首次启动自动导入）+ 意图注册表 + RAG 检索（可配置）+ Jinja2 Prompt 模板；检索为空时返回确定性引导话术，不让模型编造答案
- 对话状态持久化（MySQL），支持多轮补槽、流程中断与恢复

### 3. 业务门户 `finance-assistant/web/`

- 12 个页面、零构建：纯 HTML + 手写 CSS + 原生 JS，无外网依赖，内网离线可用
- 客户视角：我的信息、账户、交易、授信与贷款、工单
- 管理员视角：数据大盘、客户管理、客户详情、贷款审批、工单处理
- BFF 层 `/api/portal/*`：客户身份由 `X-Customer-No` 透传，管理端写操作携带 `X-Operator-No`
- 统一设计系统：冷白底 + 深板岩 + 青绿强调色，等宽数字、hover 微动效、响应式断点

---

## 工程质量与可观测性

### 质量门禁

- **CI**：GitHub Actions 两个 job（中台 / 客服）分别执行 `ruff check` 与 `pytest`，推送即校验
- **静态检查**：ruff 统一 `py312`、行宽 120、规则 `E/F/W/I/UP`
- **单元测试**：58 条（中台 53 + 客服 5），不依赖 MySQL / LLM / 外网。中台覆盖幂等、分页、校验器、
  请求 ID、限流、指标、审计脱敏、异常处理器与鉴权辅助函数；客服覆盖知识空结果兜底、意图路由与种子数据完整性

### 请求链路

- 每个响应都带 `X-Request-Id`：调用方传入合法 ID 则透传，否则自动生成，响应体 `request_id` 与之一致
- 结构化 JSON 日志自动携带 `request_id`，一次请求的访问日志、业务日志、审计记录可串联
- 全局异常兜底：业务异常 → 4xx 业务码；参数校验 → 422 字段级明细；DB 不可用 → 503；
  未捕获异常 → 500，均返回统一响应体

### 运行时可观测

| 能力 | 入口 / 说明 |
| --- | --- |
| 指标 | `GET /metrics`，Prometheus 文本格式，含请求计数与延迟直方图 |
| 限流 | 写接口按主体/IP 滑动窗口限流，默认 240 次/分钟，超限返回 429 `RATE_LIMITED` |
| 审计 | `operation_audit_log` 表记录写操作（请求 ID、渠道、操作员、耗时），凭证只存 SHA-256 摘要 |
| 审计查询 | `GET /api/v1/audit/logs`，仅员工身份可查 |

---

## 系统架构

```
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
| MySQL | `3307`（Docker） | 映射到容器内 `3306`，避开宿主机已有实例 |

---

## 目录结构

```
finance-data/
├── .github/workflows/ci.yml # CI：ruff + pytest
├── app/                     # 金融中台 FastAPI 服务（routers / 鉴权 / 幂等 / 响应体）
│   ├── middleware.py        # 请求 ID、访问日志、限流、指标、审计
│   ├── logging_config.py    # 结构化 JSON 日志
│   ├── metrics.py           # Prometheus 文本指标
│   ├── audit.py             # 写操作审计
│   └── validators.py        # 通用业务参数校验
├── generate/                # 分层测试数据生成器（9 层，全量约 5 万客户）
├── seeds/                   # 维度与产品种子数据（CSV）
├── sql/finance.sql          # 建表脚本
├── tests/
│   ├── unit/                # 53 条纯逻辑单元测试（不依赖 MySQL）
│   └── *.py                 # 接口链路与路由覆盖测试
├── docs/screenshots/        # README 截图
├── 文档/                     # 设计文档（总览 + 客服 6 篇 + Docker 部署）
│   └── 完善/                 # 代码补强实施计划与阶段汇报
├── docker/                  # docker-compose.yaml / docker-compose.full.yaml
├── init_db.py               # 建库建表
└── finance-assistant/       # 智能客服 + 业务门户
    ├── assistant/           # 引擎、流程、Action、知识库、仓储、门户 BFF
    ├── flow_config/         # 7 个金融对话流程（YAML）
    ├── tests/               # 客服侧单元测试（知识兜底、意图路由、种子完整性）
    ├── seeds/               # FAQ 种子数据（首次启动自动导入）
    └── web/                 # 12 个页面 + app.css / api.js / nav.js
```

---

## 快速开始

### 方式一：Docker 一键全栈（推荐）

前置：Docker Desktop 已启动，`8000` / `18083` 未被占用。

```bash
# 1. 首次初始化数据库并生成业务数据（会重建 finance 库）
docker compose -f docker/docker-compose.full.yaml --profile init run --rm finance-data-init

# 2. 构建并启动 mysql + 中台 + 客服
docker compose -f docker/docker-compose.full.yaml up -d --build
```

打开：

- 业务门户：<http://127.0.0.1:18083/>
- 客服接口：<http://127.0.0.1:18083/docs>
- 中台接口：<http://127.0.0.1:8000/docs>

国内网络建议先声明镜像源再执行（PowerShell）：

```powershell
$env:PYTHON_IMAGE="docker.m.daocloud.io/library/python:3.12-slim"
$env:MYSQL_IMAGE="docker.m.daocloud.io/library/mysql:8.0"
```

### 方式二：本地开发

需要 Python 3.12、MySQL 8.0、[uv](https://docs.astral.sh/uv/)。

```bash
# 中台
uv sync
uv run init_db.py                        # 建库建表
uv run -m generate.main --profile full   # 生成测试数据（smoke 为小数据量）
uv run -m app.main                       # http://127.0.0.1:8000

# 客服 + 门户（另开终端）
cd finance-assistant
uv sync
uv run python main.py                    # http://127.0.0.1:18083
```

---

## 配置说明

两个工程各有自己的 `.env`（均已在 `.gitignore` 中排除，不会提交）。

**中台 `finance-data/.env`**

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `DB_HOST` / `DB_PORT` | `127.0.0.1` / `3306` | MySQL 连接 |
| `DB_USER` / `DB_PASSWORD` | `root` / `******` | 数据库账号 |
| `DB_NAME` | `finance` | 业务库 |
| `APP_PORT` | `8000` | 服务端口 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `RATE_LIMIT_PER_MINUTE` | `240` | 写接口限流阈值，设为 `0` 关闭 |
| `METRICS_ENABLED` | `1` | 设为 `0` 关闭 `/metrics` |

**客服 `finance-assistant/.env`**

| 变量 | 说明 |
| --- | --- |
| `LLM_MODEL` / `llm_api_key` / `llm_base_url` | OpenAI 兼容大模型接口（任意供应商均可） |
| `database_url` | 客服自身库，如 `mysql+aiomysql://root:***@127.0.0.1:3306/finance_assistant` |
| `finance_api_base_url` | 中台地址，默认 `http://127.0.0.1:8000` |
| `finance_channel_code` | 渠道编码，默认 `MOBILE_BANK` |
| `finance_operator_no` | 员工编号，默认 `EMP000001` |
| `demo_customer_no` | 默认客户号，默认 `CUS00000001` |
| `finance_rag_base_url` | 知识库检索服务；留空时仅使用 FAQ（已内置 20 条种子数据） |
| `finance_db_url` | 中台业务库只读连接，管理端列表与大盘依赖它 |
| `APP_HOST` / `APP_PORT` | `127.0.0.1` / `18083` |

---

## 演示身份

| 视角 | 身份 | 说明 |
| --- | --- | --- |
| 客户 | `CUS00000001` | 门户右上角可切换任意客户号 |
| 管理员 | `EMP000001` | 审批、工单处理需带操作员编号 |

身份切换后，门户所有请求都会以新身份调用中台，越权访问会被中台拒绝。

---

## 一次完整的贷款闭环

1. 客户在「授信与贷款」选择产品与金额提交申请 → 中台冻结对应授信额度
2. 管理员在「贷款审批」通过 → 中台生成合同
3. 门户自动补齐合同文件记录 → 签约 → 全额放款
4. 放款后冻结额度转为已用额度，合同状态变为 `active`，冻结金额归零

审批动作若自动签约或放款失败，审批结果仍然保留，并在提示中给出失败原因。

---

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [文档/README.md](文档/README.md) | 项目总览、架构、快速开始与演示身份 |
| [文档/01-环境与启动.md](文档/01-环境与启动.md) | 环境、`.env`、演示身份、启动顺序、接口与错误码 |
| [文档/02-流程与槽位.md](文档/02-流程与槽位.md) | YAML 写法、步骤类型、槽位清单与 7 个流程 |
| [文档/03-Action与对象消息.md](文档/03-Action与对象消息.md) | Action 机制、6 个 Action、对象消息填槽 |
| [文档/04-知识检索与Prompt.md](文档/04-知识检索与Prompt.md) | 意图、Provider、FAQ、RAG 与四个 Prompt |
| [文档/05-测试验收.md](文档/05-测试验收.md) | 验收用例、联调脚本、异常、风险与 DoD |
| [文档/06-Docker部署与启动.md](文档/06-Docker部署与启动.md) | Docker Compose 全栈部署与 FAQ |
| [文档/完善/00-补强实施计划.md](文档/完善/00-补强实施计划.md) | 分模块补强路线：健壮性、并发、RAG、SSE、可观测性 |
| [文档/完善/01-阶段汇报-M0-M1.md](文档/完善/01-阶段汇报-M0-M1.md) | 基线治理与中台健壮性改动清单、测试教程与复核记录 |
| [文档/全流程和全类图/](文档/全流程和全类图/) | 整体流程详解与模型类图详解 |

---

## 说明

- 全部数据由 `generate/` 脚本随机生成，客户、账户、合同、流水均不对应真实机构或个人。
- 项目中不含任何真实密钥；运行前请自行配置 `.env`，并确保不将其提交到公开仓库。
- 门户的管理端身份校验为演示级实现（客户号即身份），生产环境应替换为登录态与 RBAC。
