# 06 Docker 部署与启动

本文把「MySQL + 金融中台 finance-data + 客服 finance-assistant」三件套用 Docker Compose 一次拉起，并按顺序给出可复制的验证命令。

适用场景：

- 换机器后快速复现整套环境；
- 不想在本机装 Python 3.12 / MySQL；
- 需要给同事或评审一个「一条命令起全栈」的入口。

---

## 1. 部署产物

| 文件 | 作用 |
| --- | --- |
| `finance-data/Dockerfile` | 金融中台镜像，`python:3.12-slim` + uv 装依赖，启动 `python -m app.main` |
| `finance-data/finance-assistant/Dockerfile` | 客服镜像，启动 `python main.py` |
| `finance-data/docker/docker-compose.full.yaml` | 编排：mysql + 一次性初始化 + 两个服务 |
| `finance-data/.dockerignore`、`finance-assistant/.dockerignore` | 把 `.env`、`.venv`、`__pycache__` 挡在构建上下文外，密钥不进镜像 |

镜像与容器：

| 项 | 值 |
| --- | --- |
| 中台镜像 | `finance-data:local` |
| 客服镜像 | `finance-assistant:local` |
| 容器名 | `finance-mysql`、`finance-data`、`finance-assistant` |
| Compose 项目名 | `finance-stack` |
| 数据卷 | `finance-stack_mysql-data` |

端口：

| 服务 | 宿主机 | 容器内 | 说明 |
| --- | --- | --- | --- |
| finance-assistant | `18083` | `18083` | 网页 `http://127.0.0.1:18083/`，接口 `/api/chat` |
| finance-data | `8000` | `8000` | Swagger `http://127.0.0.1:8000/docs` |
| mysql | `127.0.0.1:3307` | `3306` | 只绑定本机；避开宿主机已有的 3306 |

> 容器之间用服务名互访：客服的 `FINANCE_API_BASE_URL=http://finance-data:8000`，
> 两个服务连库都用 `mysql:3306`，不走宿主机端口。

---

## 2. 前置条件

1. Docker Desktop 已安装并**处于运行状态**（`docker info` 能返回 ServerVersion）。
2. 宿主机 `8000`、`18083` 没有被占用：

```powershell
Get-NetTCPConnection -LocalPort 8000,18083 -State Listen -ErrorAction SilentlyContinue
```

有输出就先停掉本机用 `.venv` 跑的服务，否则容器起不来（端口冲突）。

3. `finance-data/finance-assistant/.env` 存在，且 `LLM_API_KEY` 有效。
   该文件通过 `env_file` 注入容器，不会被打进镜像。

---

## 3. 关键变量

Compose 支持用环境变量覆盖，全部有默认值：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `MYSQL_IMAGE` | `mysql:8.0` | MySQL 镜像，网络慢时换成镜像站 |
| `PYTHON_IMAGE` | `python:3.12-slim` | 两个应用镜像的基础镜像 |
| `PIP_INDEX_URL` | `https://pypi.tuna.tsinghua.edu.cn/simple` | 构建期 pip / uv 依赖源 |
| `MYSQL_ROOT_PASSWORD` | `123456` | MySQL root 密码，同时用于中台与客服连库 |
| `GENERATE_PROFILE` | `full` | 初始化数据规模，`full` 约 12 分钟，`smoke` 快很多 |

> 国内网络下 Docker Hub 常被限速（层卡在 `0B`），建议在启动前先声明镜像站变量。
> 本文示例使用 `docker.m.daocloud.io`；若你的网络可直连 Docker Hub，可以不加这两行。

PowerShell 里的 `$env:` 只对当前窗口有效，新开终端需要重新设置。

---

## 4. 启动步骤

所有命令在 `finance-data/docker` 目录执行。

### 4.1 声明镜像源

```powershell
cd "d:\dev\workspace\23_电商小二\尚硅谷大模型项目实战之掌柜小二实战\finance-data\docker"

$env:PYTHON_IMAGE="docker.m.daocloud.io/library/python:3.12-slim"
$env:MYSQL_IMAGE="docker.m.daocloud.io/library/mysql:8.0"
```

### 4.2 首次初始化数据（只做一次）

```powershell
docker compose -f docker-compose.full.yaml --profile init run --rm finance-data-init
```

这一步会：

1. 启动 `finance-mysql` 并等待健康；
2. 执行 `init_db.py`：**DROP 并重建 `finance` 库**，导入 `sql/finance.sql`；
3. 执行 `python -m generate.main --profile full` 生成业务数据。

看到 `generated data validation passed` 与 `Database connection closed` 即成功。

- 想快一点：先 `$env:GENERATE_PROFILE="smoke"` 再执行；
- **库里有数据时不要重复执行**，它会清空重建。

### 4.3 构建并启动全栈

```powershell
docker compose -f docker-compose.full.yaml up -d --build
```

首次构建约 3~5 分钟（要下载依赖）。

`--build` 只在「代码或依赖改过」时才需要。**日常启动不用带它**：

```powershell
docker compose -f docker-compose.full.yaml up -d
```

容器已存在时，`up -d` 只是把停掉的容器拉起来，不重建镜像、不动数据。

### 4.4 查看状态

```powershell
docker compose -f docker-compose.full.yaml ps
```

期望三个容器都是 `Up ... (healthy)`：

```text
finance-mysql       Up (healthy)   127.0.0.1:3307->3306
finance-data        Up (healthy)   0.0.0.0:8000->8000
finance-assistant   Up (healthy)   0.0.0.0:18083->18083
```

> 中台的健康检查会同时校验「进程 + 数据库连接」。如果显示 `unhealthy` 且日志报
> `Unknown database 'finance'`，说明还没做 4.2 的初始化。

---

## 5. 验证链路

### 5.1 中台接口

```powershell
$h = @{
  Authorization    = "Bearer CUS00000001"
  "X-Channel-Code" = "MOBILE_BANK"
  "X-Request-Id"   = [guid]::NewGuid().ToString()
}
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/customers/CUS00000001/accounts" `
  -Headers $h
```

期望 `code = 0`，`data.list` 中有 `ACC0000000001` 等账户。

### 5.2 网页客服

浏览器打开 `http://127.0.0.1:18083/`，应看到聊天界面；点快捷问题「帮我查一下余额」，
约 2~5 秒返回真实账户余额。

### 5.3 接口对话

```powershell
$body = @{ sender_id = "docker_test_01"; text = "帮我查一下余额" } | ConvertTo-Json
Invoke-RestMethod `
  -Uri "http://127.0.0.1:18083/api/chat" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

期望返回 `messages` 中包含账户列表。

> 不要用 `curl.exe -d "{\"...\"}"` 这种写法：PowerShell 会吞掉转义的反斜杠，
> 服务端会收到非法 JSON 并返回 `json_invalid`。
>
> 控制台中文显示乱码时，先执行 `[Console]::OutputEncoding = [Text.Encoding]::UTF8`。

### 5.4 数据落库

客服会话状态存在 `finance_assistant` 库：

```powershell
docker exec -it finance-mysql mysql -uroot -p123456 finance_assistant -e "SHOW TABLES;"
```

应看到 `dialogue_states`、`faq_items`（由客服服务启动时自动建表）。

---

## 6. 日常操作

| 目的 | 命令 |
| --- | --- |
| 启动（已构建过） | `docker compose -f docker-compose.full.yaml up -d` |
| 暂停（保留容器，下次秒起） | `docker compose -f docker-compose.full.yaml stop` |
| 从暂停继续 | `docker compose -f docker-compose.full.yaml start` |
| 停止并删除容器（保留数据） | `docker compose -f docker-compose.full.yaml down` |
| 重新构建并启动（改代码后） | `docker compose -f docker-compose.full.yaml up -d --build` |
| 重启单个服务 | `docker compose -f docker-compose.full.yaml restart finance-assistant` |
| 看日志 | `docker compose -f docker-compose.full.yaml logs -f finance-assistant` |
| 看中台日志 | `docker compose -f docker-compose.full.yaml logs -f finance-data` |
| 进客服容器 | `docker exec -it finance-assistant sh` |
| 进 MySQL | `docker exec -it finance-mysql mysql -uroot -p123456` |
| 彻底重置（含数据） | `docker compose -f docker-compose.full.yaml down -v`，再重做 4.2 |

三个「停止」的区别：

| 命令 | 容器 | 数据 | 再启动 |
| --- | --- | --- | --- |
| `stop` | 保留，只是停下 | 保留 | `start`，秒级恢复 |
| `down` | 删除 | 保留（卷还在） | `up -d`，重新创建容器 |
| `down -v` | 删除 | 清空 | 必须先重做 4.2 初始化 |

数据在 `finance-stack_mysql-data` 卷里，`stop` 和 `down` 都不会删除；只有 `down -v` 才清空。

**日常启动不需要 `--build`，也不需要重新初始化**，直接 `up -d` 即可。`--build` 只在改过
Dockerfile、`pyproject.toml`/`uv.lock` 或业务代码后才需要（代码是在镜像里的，不重建就不生效）。

### 6.1 在 Docker Desktop 里手动启动/停止

可以。创建过一次容器后，Docker Desktop 的 **Containers** 页面会按 Compose 项目分组，
本项目显示为 **`finance-stack`**，展开后是 `finance-mysql`、`finance-data`、`finance-assistant` 三个容器。

- 整个项目一起启动/停止：在 `finance-stack` 分组右侧点 ▶（Start）/ ■（Stop）。
- 单个服务：展开分组后，在对应容器行右侧点 ▶ / ■ / 垃圾桶。
- 也可以在分组上右键，选择 Start / Stop / Restart。

前提与限制：

1. **容器必须先由命令行创建过**（即执行过 4.3）。从没跑过 `up -d` 的项目不会出现在 Containers 里。
2. 在 Desktop 里点 Start，等价于 `docker compose start`：**只拉起已有容器，不重建镜像**。
   改过代码、Dockerfile、`.env` 或 compose 文件后，Desktop 点击不会生效，必须回到命令行：

   ```powershell
   docker compose -f docker-compose.full.yaml up -d --build
   ```

3. 执行过 `docker compose down` 后，容器被删除，Desktop 里这个分组就消失了（卷仍保留）；
   需要重新用 `up -d` 创建，之后才能继续用 Desktop 点击。
4. Desktop 里点 Start 是按依赖顺序恢复，但不会帮你重跑 4.2 的初始化任务，
   也不会修复 unhealthy 状态；启动失败优先看容器日志，或直接用 `up -d`。

---

## 7. 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 构建卡在 `0B / 12.12MB` | Docker Hub 拉取被限速 | 按 4.1 声明 `PYTHON_IMAGE` / `MYSQL_IMAGE` 镜像站 |
| `pip install uv` 报 `SSLError` | 容器内直连 pypi.org 失败 | 已默认走清华源；如仍失败，覆盖 `PIP_INDEX_URL` |
| `frappe`/`deb.debian.org` 连接失败 | apt 源不可达 | 镜像不再执行 apt 安装，无需处理；旧镜像请重新构建 |
| `Bind for 0.0.0.0:8000 failed` | 宿主机端口被占用 | 先停本机服务，或改 compose 的端口映射 |
| `finance-data` 一直 `unhealthy` | 数据未初始化 | 执行 4.2，然后 `docker compose ... up -d` |
| 客服日志报连不上 `mysql` | MySQL 未健康 | `docker compose ... ps` 检查 mysql；必要时看 `logs mysql` |
| 对话返回「服务暂时不可用」 | 客服到中台链路异常 | 查 `logs finance-data`；确认 `FINANCE_API_BASE_URL` 未被改回 127.0.0.1 |
| 修改 `.env` 不生效 | 容器没重建 | `docker compose -f docker-compose.full.yaml up -d --force-recreate finance-assistant` |
| Docker Desktop 里找不到 `finance-stack` | 容器已被 `down` 删除，或从未 `up` 过 | 先在命令行执行 `up -d`，之后分组才会出现 |
| Desktop 点 Start 后仍是旧代码/旧配置 | 点击只恢复容器，不重建镜像 | 改用 `up -d --build`（配置变更加 `--force-recreate`） |
| 管理员审批贷款报「客户缺少可用还款账户」 | 测试数据把正常账户状态生成成了 `normal`，审批接口只认 `active` | 执行 7.1 的 SQL 修正账户状态 |

### 7.1 审批贷款报「客户缺少可用还款账户」

中台审批通过时会自动创建贷款合同，并挑选同币种、状态为 `active` 的账户作为还款账户
（`app/routers/loans.py` 的 `_customer_repayment_account`）。而数据生成器把正常账户写成了
`normal`，所以所有客户的审批都会命中这个报错，账户交易类接口也会因同样的原因被拒绝。

容器内执行（在 `finance-data/docker` 目录，密码默认 `123456`，如改过请替换）：

```powershell
docker compose -f docker-compose.full.yaml exec -T mysql `
  mysql -uroot -p123456 finance `
  -e "UPDATE bank_account SET account_status='active' WHERE account_status='normal';"
```

本地 MySQL 直接执行：

```sql
UPDATE bank_account SET account_status='active' WHERE account_status='normal';
```

执行后可核对状态分布：

```sql
SELECT account_status, COUNT(*) FROM bank_account GROUP BY account_status;
```

注意：每次重新执行 4.2 的数据初始化后，账户状态都会变回 `normal`，需要重新执行本条 SQL。
账户被标记为 `closed`（销户）的不会更新，仍然不能作为还款账户。

合规提醒：`.env` 中的 `LLM_API_KEY` 通过 `env_file` 注入，`.dockerignore` 已排除该文件，
不要把密钥写进 Dockerfile 或 compose 的 `environment` 里。

---

## 8. 与本地启动的关系

| 方式 | 优点 | 注意 |
| --- | --- | --- |
| Docker Compose | 一条命令起全栈，环境隔离 | 占用 8000 / 18083，要先停本地服务 |
| 本地 `.venv` | 改代码即时生效，调试方便 | 需要本机有 MySQL，且与容器端口互斥 |

两者共用同一套 `.env` 语义，但数据库地址不同：容器里是 `mysql:3306`，
本地是 `127.0.0.1:3306`。切换时不要互相覆盖配置文件。

---

## 9. 验收清单

- [ ] `docker info` 能返回 ServerVersion
- [ ] `finance-data-init` 跑完并输出 `generated data validation passed`
- [ ] `ps` 中三个容器都是 `healthy`
- [ ] `/customers/CUS00000001/accounts` 返回 `code = 0`
- [ ] `http://127.0.0.1:18083/` 能打开聊天界面并返回真实余额
- [ ] `finance_assistant` 库中有 `dialogue_states` 表
- [ ] `down` 后再次 `up -d`，数据仍在
