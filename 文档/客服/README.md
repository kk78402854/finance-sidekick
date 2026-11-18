# 金融智能客服助手（finance-assistant）

面向银行零售业务的对话式客服工程。它把金融中台（`finance-data`，FastAPI，端口 8000）的账户、交易、授信、贷款、理财、工单接口，包装成一条可运营的对话链路：

用户消息 → LLM 意图识别 → 结果校验 → 任务流程 / 知识检索 / 闲聊 → 金融接口 → LLM 润色 → 回复。

- 客服服务端口：**18083**
- 金融中台端口：**8000**（前缀 `/api/v1`）
- 独立数据库：**finance_assistant**（保存会话状态与 FAQ）
- 代码包名：`assistant`

## 1. 能力清单

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

## 2. 目录结构

```text
finance-assistant/
├── main.py                      # 启动入口：初始化对话引擎并拉起 FastAPI
├── pyproject.toml               # 依赖声明
├── .env                         # 大模型、金融中台、数据库、端口配置
├── flow_config/
│   └── user_flows.yml           # 槽位定义 + 全部业务流程
├── web/
│   └── index.html               # 单页网页聊天界面（FastAPI 挂载在 /）
└── assistant/
    ├── api/                     # 对外 HTTP 接口：/api/chat、/api/chat/history
    ├── engine/                  # 总装工厂 builder、对话引擎 dialogue_engine
    ├── plan/                    # LLM 意图识别 turn_planner、结果校验 validator
    ├── task/
    │   ├── flow/                # YAML 流程模型、加载、步骤、跳转
    │   ├── flowexecutor/        # 按步骤推进流程
    │   ├── action/              # Action 基类、注册表、6 个金融 Action
    │   ├── response/            # 回复模板渲染（jinja2）
    │   ├── command/             # start_flow / set_slots / resume / cancel 执行
    │   └── tasklifecycle/       # 任务开始、切换、恢复、取消的提示
    ├── knowledge/               # 知识意图、Provider、检索入口、LLM 润色
    ├── clarify/                 # 意图不清时的澄清回复
    ├── chitchat/                # 闲聊
    ├── prompts/jinja2/          # 四个提示词模板
    ├── repository/              # 会话状态持久化、FAQ 查询
    ├── domain/                  # 消息、状态、对象消息到槽位的映射
    ├── service/                 # 对话服务编排
    ├── conf/config.py           # pydantic-settings 读取 .env
    └── utils/                   # 数据库、HTTP、金融接口客户端、LLM
```

## 3. 快速开始

```bash
# 1. 准备数据库（只要建库，表由服务启动时自动创建）
mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS finance_assistant DEFAULT CHARSET utf8mb4;"

# 2. 安装依赖（任选其一）
uv sync
# 或
pip install -e .

# 3. 先启动金融中台 finance-data（8000），再启动本服务
python main.py
```

启动成功后：

- 网页聊天界面：`http://127.0.0.1:18083/`（`web/index.html` 单页，无需构建）
- 接口文档：`http://127.0.0.1:18083/docs`

最小请求（PowerShell）：

```powershell
$body = @{ sender_id = "u1001"; text = "你好" } | ConvertTo-Json
Invoke-RestMethod `
  -Uri "http://127.0.0.1:18083/api/chat" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

## 4. 文档索引

| 文档 | 内容 |
| --- | --- |
| [01-环境与启动.md](01-环境与启动.md) | 依赖、建库、`.env` 全量说明、启动顺序、接口示例 |
| [02-流程与槽位.md](02-流程与槽位.md) | `user_flows.yml` 写法、7 条流程、槽位语义、条件跳转 |
| [03-Action与对象消息.md](03-Action与对象消息.md) | Action 注册机制、6 个 Action、对象消息填槽 |
| [04-知识检索与Prompt.md](04-知识检索与Prompt.md) | 知识意图、Provider、FAQ 表、RAG、四个 Prompt |
| [05-测试验收.md](05-测试验收.md) | 验收用例、异常码、联调脚本、常见问题 |
| [06-Docker部署与启动.md](06-Docker部署与启动.md) | Compose 编排、初始化数据、启动验证、排障、重置 |

金融中台自身的接口与数据说明见上级目录 `finance-data/文档/`。
