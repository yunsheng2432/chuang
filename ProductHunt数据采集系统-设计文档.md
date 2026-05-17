# ProductHunt 每日热门项目数据采集系统 — 设计文档

## 一、可行性评估

**结论：容易实现，且有多种成熟方案可选。**

ProductHunt 的数据采集有两条主流路径：

| 方案 | 难度 | 稳定性 | 适用场景 |
|------|------|--------|----------|
| **官方 GraphQL API v2** | 低 | 高（官方支持） | 长期运行、个人/商业项目 |
| **Web 爬虫（Playwright/Selenium）** | 中 | 中（页面结构可能变化） | 快速原型、绕过 API 限制 |

**推荐方案：官方 GraphQL API v2 + 定时调度**，理由：
- 有官方文档和开发者 token，无需破解反爬机制
- 返回结构化 JSON 数据，解析零成本
- 免费额度对每日统计场景绰绰有余

---

## 二、系统架构总览

```
┌──────────────────────────────────────────────────┐
│                  调度层（Scheduler）                │
│               Python / GitHub Actions             │
│         每日定时触发（如北京时间 09:00）             │
└─────────────────────┬────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────┐
│                 数据采集层（Fetcher）               │
│                   Python + requests               │
│    调用 ProductHunt GraphQL API，获取当日 Top N   │
└─────────────────────┬────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────┐
│                数据处理层（Processor）              │
│                      Python                       │
│   字段提取、清洗、去重、翻译（可选）、结构化存储      │
└─────────────────────┬────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────┐
│                  存储层（Storage）                  │
│              SQLite / PostgreSQL / CSV            │
│         项目名、简介、投票数、功能标签、日期          │
└─────────────────────┬────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────┐
│              展示/通知层（Presentation）            │
│           Markdown 报告 / HTML / 飞书/钉钉通知      │
│            可选：Grafana / Streamlit 看板          │
└──────────────────────────────────────────────────┘
```

---

## 三、模块详细设计

### 模块 1：调度层（Scheduler）✅ 已实现

| 项目 | 说明 |
|------|------|
| **职责** | 每日定时触发采集任务，串联所有下游模块 |
| **选用方案** | GitHub Actions（方案 B） |
| **组成文件** | `.github/workflows/daily-fetch.yml`、`config.py`、`main.py` |
| **输入** | 无（时钟驱动，支持手动触发） |
| **输出** | 调用采集脚本，提交结果回仓库 |

#### 已实现文件及职责

| 文件 | 职责 |
|------|------|
| `.github/workflows/daily-fetch.yml` | 定义定时触发规则（UTC 01:00 = 北京时间 09:00）、安装依赖、注入 Secrets、执行 `main.py`、用 `git-auto-commit-action` 将新数据自动提交回仓库 |
| `config.py` | 集中管理所有配置：API Token（从环境变量读取）、采集数量、数据库/报告路径、日志格式。其余模块统一 `import config`，不直接触碰 `os.environ` |
| `main.py` | 调度入口脚本。按顺序串联 4 个下游模块（fetcher → processor → storage → report），每个模块以 `try/except ImportError` 动态加载——未实现的模块会打印 warning 并跳过，已实现的则正常执行 |

#### 为什么不需要本地运行

GitHub Actions 在 GitHub 的 Ubuntu 虚拟机上运行整个流程：
1. 到点自动启动虚拟机
2. 拉取仓库代码
3. 安装 Python + 依赖
4. 执行 `python main.py`
5. 将采集结果（db 文件、日报）作为新 commit 推回仓库

全程无需本地机器开机。唯一需要在本地做的事：首次 push 代码 + 在 GitHub 仓库 Settings → Secrets 里添加 `PRODUCTHUNT_TOKEN`。

#### 手动触发支持

除了定时触发，`daily-fetch.yml` 还配置了 `workflow_dispatch`，允许在 GitHub Actions 页面手动点击 "Run workflow" 并指定 `date_override` 参数来补采某一天的数据。

---

### 模块 2：数据采集层（Fetcher）✅ 已实现

| 项目 | 说明 |
|------|------|
| **职责** | 通过 ProductHunt GraphQL API 拉取指定日期投票量最高的项目列表 |
| **实现文件** | `fetcher.py` |
| **依赖** | `config.py`（读取 Token 和 API 地址） |
| **输入** | 数量上限 n（默认 20） |
| **输出** | GraphQL 原始响应 dict，结构 `{"data": {"posts": {"edges": [...]}}}` |

#### 已实现的特性

| 特性 | 实现方式 |
|------|----------|
| **GraphQL 查询** | 按 `order: VOTES` 降序、`featured: true`、`postedAfter` 时间筛选 |
| **自动日期计算** | 默认采集 UTC 昨天；也可通过 `FETCH_DATE_OVERRIDE` 环境变量手动指定 |
| **认证校验** | 启动时检查 Token 是否为空，给出明确的获取指引 |
| **指数退避重试** | 最多 3 次（2s/4s/8s），处理 429 限流、5xx 服务端错误、网络超时 |
| **GraphQL errors 处理** | 即使 HTTP 200，如果响应体含 `errors` 字段也会抛出异常 |

#### Token 获取步骤

1. 访问 [ProductHunt API Dashboard](https://www.producthunt.com/v2/oauth/applications)
2. 创建 Application → 获取 **Developer Token**
3. 本地开发：写入 `.env` 文件（`PRODUCTHUNT_TOKEN=xxx`）
4. CI 环境：写入 GitHub 仓库 Settings → Secrets → 添加 `PRODUCTHUNT_TOKEN`

---

### 模块 3：数据处理层（Processor）✅ 已实现

| 项目 | 说明 |
|------|------|
| **职责** | 将 API 返回的嵌套 GraphQL JSON 清洗为扁平结构化记录，按票数降序排序 |
| **实现文件** | `processor.py` |
| **依赖** | 无（纯函数，只接收 dict） |
| **输入** | `fetcher.fetch_daily_top()` 返回的原始 JSON |
| **输出** | `list[dict]`，每条记录含 9 个字段，按 votes_count 降序 |

#### 输出字段

| 字段 | 类型 | 来源 | 默认值 |
|------|------|------|--------|
| `name` | str | `node.name` | `""` |
| `tagline` | str | `node.tagline` | `""` |
| `description` | str | `node.description` | `""`（截断至 500 字符） |
| `votes_count` | int | `node.votesCount` | `0` |
| `website` | str | `node.website` | `""` |
| `url` | str | `node.url` | `""` |
| `topics` | list[str] | `node.topics.edges[].node.name` | `[]` |
| `thumbnail` | str | `node.thumbnail.url` | `""` |
| `created_at` | str | `node.createdAt` | `""` |

#### 空值防御

GraphQL 响应中字段可能为 `null`、缺失或嵌套对象为空。`processor.py` 已在以下层级做了 `dict.get()` + `or {}` 防护：
- `node.topics` 为 null
- `node.topics.edges[i].node` 为 null
- `node.thumbnail` 为 null
- 整个 `edges` 列表为空或数据路径不存在时返回 `[]`

---

### 模块 4：存储层（Storage）✅ 已实现

| 项目 | 说明 |
|------|------|
| **职责** | 将处理后的项目记录持久化，提供历史查询接口 |
| **实现文件** | `storage.py` |
| **选型** | SQLite（单文件零依赖，WAL 模式写） |
| **输入** | `processor.process_posts()` 输出的记录列表 + 日期字符串 |
| **输出** | 写入 `producthunt.db`，同一天重复执行自动覆盖旧数据 |

#### 公开接口

| 函数 | 用途 |
|------|------|
| `save_to_db(posts, fetch_date)` | 批量写入当日 Top N 记录 |
| `load_history(days=30)` | 查询最近 N 天历史，返回 `list[dict]` |
| `get_latest_date()` | 获取数据库中最新的采集日期 |

#### 建表结构

```sql
daily_top_products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fetch_date  DATE NOT NULL,
    rank        INTEGER NOT NULL,
    name        TEXT NOT NULL,
    tagline     TEXT,
    description TEXT,
    votes_count INTEGER,
    website     TEXT,
    url         TEXT,
    topics      TEXT,          -- JSON array 字符串
    thumbnail   TEXT,
    created_at  TIMESTAMP,
    UNIQUE(fetch_date, rank)   -- 防止同一天同排名重复
);
```

#### 关键设计点

- **INSERT OR REPLACE** — 基于 `UNIQUE(fetch_date, rank)` 约束，同一天第二次运行自动覆盖而非追加，避免重复数据
- **WAL 模式** — `PRAGMA journal_mode=WAL`，写不阻塞读，即使采集脚本还在跑也可以开 Streamlit 看板查询
- **路径自适应** — 相对路径自动转为相对于 `storage.py` 所在目录的绝对路径，避免从不同工作目录运行时报找不到文件
- **topics 存储** — 以 JSON 数组字符串存入，读时由调用方 `json.loads()` 还原，保持 SQLite 兼容性

---

### 模块 5：展示/通知层（Presentation）✅ 已实现

| 项目 | 说明 |
|------|------|
| **职责** | 将采集结果生成为可读的 Markdown 日报，支持 Webhook 推送到 IM 工具 |
| **实现文件** | `report.py` |
| **输入** | `processor.process_posts()` 输出的记录列表 + 日期字符串 |
| **输出** | `reports/report_YYYY-MM-DD.md` 文件；可选 Webhook 消息推送 |

#### 公开接口

| 函数 | 用途 |
|------|------|
| `generate_markdown(posts, date_str)` | 生成 Markdown 日报，写入 `reports/` 目录 |
| `push_webhook(posts, date_str, webhook_url, top_n=5)` | 推送 Top N 摘要到飞书/企业微信 Webhook |

#### 日报格式示例

```markdown
#  ProductHunt 每日热门项目 — 2026-05-16

> 统计日期：2026-05-16  |  共 20 个项目  |  自动采集于 2026-05-17 01:30 UTC

---

## 1. [AppName](https://producthunt.com/...)  —  1500 票

> A great one-liner tagline

Detailed description text (up to 300 characters)...

**标签**: AI, Productivity, Developer Tools  |  **官网**: https://example.com

---
```

#### 关键设计点

- **空值友好** — tagline 为空时显示 `(无简介)`，topics 为空时显示 `-`，description 截断至 300 字符
- **Webhook 推送** — 支持飞书/企业微信 Markdown 格式，默认推送 Top 5，失败不阻塞主流程（仅打印 warning）
- **路径自适应** — `reports/` 目录自动定位到项目根目录

---

## 四、项目文件结构（实际）

```
producthunt-daily/
├── .github/workflows/
│   └── daily-fetch.yml          # 调度层：GitHub Actions 定时触发 + 手动触发
├── config.py                    # 全局配置：环境变量、API 地址、路径、日志格式
├── main.py                      # 调度入口：按序串联 fetcher → processor → storage → report → webhook
├── fetcher.py                   # 数据采集层：GraphQL API 调用 + 重试
├── processor.py                 # 数据处理层：JSON→扁平记录 + 排序
├── storage.py                   # 存储层：SQLite 读写 + 历史查询
├── report.py                    # 展示/通知层：Markdown 日报 + Webhook 推送
├── requirements.txt             # Python 依赖（requests + python-dotenv）
├── .gitignore                   # 排除 .env 和 Python 缓存
├── .env                         # 本地开发环境变量（不入 git）
├── producthunt.db               # SQLite 数据库（运行后自动生成）
└── reports/                     # Markdown 日报存档（运行后自动生成）
    └── report_2026-05-16.md
```

---

## 五、部署与使用指南

### 5.1 前置准备

**需要准备的东西：**

| 序号 | 事项 | 说明 |
|------|------|------|
| 1 | GitHub 仓库 | 新建或使用已有仓库，用于存放代码和接收采集结果 |
| 2 | ProductHunt Developer Token | 免费申请，见下方步骤 |
| 3 | 飞书/企业微信 Webhook URL | 可选，用于将每日 Top 5 推送到 IM |

### 5.2 获取 ProductHunt API Token

**前提**：需要一个 ProductHunt 账号。如果没有，先到 [producthunt.com](https://www.producthunt.com/) 注册（支持 Google/GitHub 快捷登录）。

1. 登录后打开 [ProductHunt API Dashboard](https://www.producthunt.com/v2/oauth/applications)
2. 点击 **Create an application**
3. 填入应用名称（如 `my-daily-scraper`）和回调 URL（填 `https://localhost` 即可，本程序用的是 Developer Token 而非 OAuth，回调地址实际不会被用到）
4. 创建后在 Dashboard 中找到 **Developer Token**，点击 **Generate** 并复制

> **注意**：Developer Token 只供个人使用，不要分享或提交到公开仓库。Token 放在 Secrets 中。

### 5.3 本地开发与测试

1. **克隆仓库**
   ```bash
   git clone <你的仓库地址>
   cd producthunt-daily
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **创建 `.env` 文件**（在项目根目录 `producthunt-daily/` 下）
   ```
   PRODUCTHUNT_TOKEN=你刚才复制的developer_token
   # 以下可选：
   WEBHOOK_URL=https://hooks.example.com/your-webhook-path
   ```
   
   文件已写入 `.gitignore`，不会被 git 跟踪。

4. **手动运行一次，确认一切正常**
   ```bash
   python main.py
   ```
   
   预期输出：
   ```
   [1/4] 正在从 ProductHunt API 拉取数据...
   [1/4] 数据拉取完成，共 20 条原始记录
   [2/4] 正在清洗和排序数据...
   [2/4] 数据处理完成，有效记录 20 条
   [3/4] 正在写入数据库...
   [3/4] 数据库写入完成
   [4/4] 正在生成 Markdown 日报...
   [4/4] 日报已生成至 reports/report_2026-05-16.md
   ===== 采集完成 =====
   ```

5. **补采指定日期**（可选）：设置 `FETCH_DATE_OVERRIDE` 环境变量
   ```bash
   # Windows PowerShell:
   $env:FETCH_DATE_OVERRIDE="2026-05-10"; python main.py
   # Linux/Mac:
   FETCH_DATE_OVERRIDE=2026-05-10 python main.py
   ```

### 5.4 部署到 GitHub Actions（自动化）

1. **将代码推送到 GitHub**
   ```bash
   git add .
   git commit -m "feat: ProductHunt daily scraper"
   git push origin main
   ```

2. **在 GitHub 仓库配置 Secrets**
   
   打开仓库页面 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，添加以下 Secrets：

   | Secret 名称 | 值 | 是否必需 |
   |-------------|----|-----------|
   | `PRODUCTHUNT_TOKEN` | 你的 Developer Token | ✅ 必需 |
   | `WEBHOOK_URL` | 飞书/企业微信 Webhook 地址 | ❌ 可选 |

3. **验证定时任务已生效**
   
   打开仓库页面 → **Actions** 标签页 → 左侧找到 `Daily ProductHunt Fetch` → 可以看到 workflow 已注册。
   
   - **想立刻测试**：点击右侧 **Run workflow** 下拉 → 绿色 **Run workflow** 按钮，填入日期（留空自动采集昨天）→ 手动触发一次。

4. **自动化流程**
   
   之后每天的 UTC 01:00（北京时间 09:00），GitHub 会自动：
   - 启动 Ubuntu 虚拟机
   - 拉取最新代码
   - 安装依赖
   - 执行 `python main.py`
   - 将 `producthunt.db` 和 `reports/*.md` 作为一个新 commit 推回仓库

5. **查看结果**
   
   每次运行后，仓库根目录会出现：
   - `producthunt.db`：SQLite 数据库，可使用 [DB Browser for SQLite](https://sqlitebrowser.org/) 或命令行查看
   - `reports/report_YYYY-MM-DD.md`：每日 Markdown 日报

### 5.5 查看历史数据

方式一：直接查看 Markdown 日报
```bash
ls reports/
# report_2026-05-14.md
# report_2026-05-15.md
# report_2026-05-16.md
```

方式二：用 Python 脚本查询数据库
```python
from storage import load_history, get_latest_date

# 查询最近 7 天的 Top 10
records = load_history(days=7)
for r in records[:10]:
    print(f"{r['fetch_date']}  #{r['rank']}  {r['name']}  {r['votes_count']}票")

# 查看最新数据日期
print(get_latest_date())
```

方式三：git log 追溯每期变化
```bash
git log --oneline -- reports/
```

---

## 六、执行流程总结

```
每日 UTC 01:00（北京时间 09:00）
    │
    ▼
GitHub Actions 启动 Ubuntu 虚拟机
    │
    ├─ 检出代码（actions/checkout）
    ├─ 安装 Python 3.12 + pip install -r requirements.txt
    ├─ 注入 Secrets（PRODUCTHUNT_TOKEN、WEBHOOK_URL）
    ├─ 执行 python main.py
    │   │
    │   ├─ [1] fetcher.fetch_daily_top()    → ProductHunt GraphQL API
    │   ├─ [2] processor.process_posts()     → 字段提取 + 排序
    │   ├─ [3] storage.save_to_db()          → 写入 SQLite
    │   ├─ [4] report.generate_markdown()    → 生成 Markdown 日报
    │   └─ [5] report.push_webhook()         → 推送 IM（可选）
    │
    └─ git-auto-commit-action 自动提交 producthunt.db + reports/ 回仓库
```

---

## 七、注意事项与常见问题

### 安全
1. **Token 绝不硬编码**。`.env` 文件仅在本地使用且已加入 `.gitignore`；CI 环境通过 GitHub Secrets 注入。
2. **`.gitignore` 已配置**排除 `.env`、`__pycache__/`、IDE 配置文件，推代码前无需手动清理。

### 时区
- GitHub Actions 使用 **UTC 时区**。`cron: "0 1 * * *"` 对应 UTC 01:00 = **北京时间 09:00**。
- `fetcher.py` 中的日期计算基于 UTC：`datetime.now(timezone.utc) - timedelta(days=1)`。
- ProductHunt 的项目按 UTC 日期发布，所以采集"UTC 昨天"即对应"北京时间昨晚到今晨"发布的项目。

### 数据延迟
- ProductHunt 每日项目的投票在发布后 24 小时内持续进行，因此采集前一天的项目数据最为准确。
- 如果某天没有采集到数据，可能是当天 ProductHunt 没有新的 featured 项目（周末/节假日少见），而非程序故障。

### 重复运行
- 无论自动触发还是手动触发多次，同一天的旧数据会被 `INSERT OR REPLACE` 覆盖，不会产生重复行。
- 日报文件也会被覆盖，始终保持最新版本。

### 手动补采
- 在 GitHub Actions 页面的 `Daily ProductHunt Fetch` → `Run workflow` → 填入 `date_override`（如 `2026-05-01`），即可补采任意历史日期。
- 本地运行：`FETCH_DATE_OVERRIDE=2026-05-01 python main.py`。

### 常见错误排查

| 报错 | 原因 | 解决方案 |
|------|------|----------|
| `PRODUCTHUNT_TOKEN 未设置` | 未配置 Token | 检查 `.env` 文件（本地）或 GitHub Secrets（CI） |
| `API 认证失败 (HTTP 401)` | Token 无效或过期 | 重新生成 ProductHunt Developer Token |
| `已重试 3 次仍不成功` | 网络或 API 故障 | 查看输出中每次重试的原因；手动再触发一次 |
| `原始数据中无项目记录` | 指定日期无 featured 项目 | 尝试另一个日期或检查 `postedAfter` 是否正确 |

---

## 八、扩展方向（后续可迭代）

- 接入 **OpenAI API** 自动生成中文摘要
- 按 **Topics 标签** 分类统计趋势
- 对接 **Notion / Airtable** 自动写入数据库
- 部署 **Streamlit 看板** 提供在线查询页面
- 多日趋势分析：哪些主题在上升、哪些类型的项目持续热门