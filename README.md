# AI 岗位备考平台（AI-JD-Aggregator）

> 聚合各企业**官方招聘页**公开的 AI 岗位 JD，用 LLM 把 JD 结构化为
> **项目能力要求 / 技术栈 / 针对性面试题**，帮助求职者从零备考。

本项目严格遵守合规边界：**只爬取企业官方招聘域名，绝不访问 BOSS 直聘、猎聘、拉勾等第三方聚合平台**。

---

## 一、项目能做什么（3 分钟了解）

1. **爬取**：每天定时从 8 家代表性企业的官方招聘页抓取 AI 岗位（字节跳动、腾讯、美团、MiniMax、智谱AI、科大讯飞、阶跃星辰、速腾聚创）
2. **结构化**：对每条 JD 调用 LLM，自动生成「项目能力要求 / 技术栈 / 5 道面试题及参考答案」
3. **展示**：网页端按公司、岗位类型、技术栈筛选浏览，JD 详情页左侧原文、右侧备考面板
4. **搜索**：跨公司搜索技术栈关键词（RAG、LoRA、多模态……）

**目录结构**

```
chat-3/
├── backend/                    # Python 爬虫 + AI 结构化
│   ├── main.py                 # 入口：爬取 → 过滤 → 入库 → 结构化
│   ├── config.py               # 全部配置项（读取 .env）
│   ├── utils.py                # 日志 / 哈希 / 重试 / 告警
│   ├── ai_filter.py            # AI 岗位过滤与 job_type 归类
│   ├── crawler/
│   │   ├── robots.py           # robots.txt 合规检查
│   │   ├── rate_limiter.py     # 3~5 秒间隔 + 每日 200 条上限
│   │   ├── base.py             # 爬虫基类（限速/重试/优雅降级）
│   │   └── adapters/           # 各企业适配器（新公司加这里）
│   ├── enrichment/llm.py       # enrich_jd()：JD 结构化核心
│   └── storage/supabase_store.py # 存储（Supabase / 本地 JSON 降级）
├── supabase/schema.sql         # 数据库建表 SQL（复制到 Supabase 执行）
├── frontend/                   # Next.js 14 前端
│   ├── app/                    # 首页 / 公司详情 / JD 详情 / 搜索
│   ├── components/             # 公司卡片 / 备考面板 / 筛选器等
│   └── lib/                    # Supabase 客户端与类型
└── .github/workflows/          # GitHub Actions 每日 06:00 定时任务
```

---

## 二、你需要准备什么（新手必看）

| 需要安装 | 下载地址 | 说明 |
|---|---|---|
| Python 3.11+ | https://www.python.org/downloads/ | 你的电脑现在是 3.9 也能跑，但推荐装 3.11 |
| Node.js 20+ | https://nodejs.org/ | 运行前端必须（当前未安装，需先装） |
| 一个 LLM API Key | OpenAI / DeepSeek / 硅基流动等 | 生成面试题用，选便宜的即可（如 DeepSeek） |
| 一个 Supabase 账号（免费） | https://supabase.com | 存数据 + 前端查询 |

---

## 三、第 1 步：本地跑通爬虫（约 15 分钟）

> 目标：不配任何 Key，先让爬虫跑起来，把结果存到本地 JSON 里。

### 3.1 安装 Python 依赖

在项目根目录打开 PowerShell，执行：

```powershell
# 创建虚拟环境（推荐，隔离依赖）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 的浏览器内核（Chromium，约 150MB）
python -m playwright install chromium
```

> 如果 `python` 命令找不到，试试 `py`（Windows 上的 Python 启动器）。

### 3.2 跑一次爬虫（只爬 1 家，验证环境）

```powershell
python backend/main.py --adapter bytedance --no-enrich
```

- `--adapter bytedance`：只爬字节跳动（其余公司稍后一起跑）
- `--no-enrich`：跳过 LLM 结构化（还没配 Key）

**预期看到**：日志中出现「已加载 robots.txt 规则」「AI 岗位过滤完成：N 条命中」。
数据会写入 `data/local_store.json`（Supabase 未配置时自动降级，无需任何操作）。

> ⚠️ 如果某家返回「列表为空」，通常是网站改版导致选择器失效——这不影响其它公司，见第八节「故障排查」。

### 3.3 配置 LLM，生成备考内容

1. 复制 `.env.example` 为 `.env`：

   ```powershell
   Copy-Item .env.example .env
   ```

2. 用记事本打开 `.env`，填入（以 DeepSeek 为例，最便宜）：

   ```ini
   OPENAI_API_KEY=sk-你的DeepSeek密钥
   OPENAI_BASE_URL=https://api.deepseek.com/v1
   LLM_MODEL=deepseek-chat
   CONTACT_EMAIL=你的邮箱@example.com
   ```

3. 对已爬取的 JD 跑结构化：

   ```powershell
   python backend/main.py --enrich-only
   ```

   看到「结构化完成：成功 N / 失败 0」就 OK 了。
   打开 `data/local_store.json` 就能看到每条 JD 的 `project_requirements`、`tech_stack`、`interview_questions`。

### 3.4 全部公司一起跑

```powershell
python backend/main.py
```

> 首次会逐家检查 robots.txt、每请求间隔 3~5 秒，8 家跑完大约 10~30 分钟，耐心等待即可。

### 3.5 自测（可选）

改过代码后想确认核心逻辑没坏，运行内置冒烟测试（不联网、不调 LLM）：

```powershell
python smoke_test.py
```

看到「23 通过 / 0 失败」即正常。

---

## 四、第 2 步：搭建 Supabase 数据库（免费，约 10 分钟）

1. 注册 https://supabase.com → New project → 随便起名，地区选 **Singapore**（离国内近）
2. 创建完成后，左侧菜单 **SQL Editor** → New query → 把 [supabase/schema.sql](supabase/schema.sql) 全部内容粘贴进去 → **Run**
3. 左侧 **Project Settings → API** 页面，抄下三个值：
   - `Project URL` → 填到 `.env` 的 `SUPABASE_URL`
   - `service_role`（服务端密钥）→ 填到 `.env` 的 `SUPABASE_SERVICE_ROLE_KEY`（**只给爬虫用，不要泄露**）
   - `anon public`（匿名密钥）→ 填到 `frontend/.env.local` 的 `NEXT_PUBLIC_SUPABASE_ANON_KEY`

4. 重新跑一次爬虫，数据就会写入云端数据库：

   ```powershell
   python backend/main.py
   ```

   到 Supabase 控制台 **Table Editor** 看 `jobs` 表，有数据就成功了。

---

## 五、第 3 步：运行前端（约 10 分钟）

> 前提：已安装 Node.js 20+。

### 5.1 安装依赖并启动

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local   # 填好 NEXT_PUBLIC_SUPABASE_URL 和 ANON KEY
npm run dev
```

浏览器打开 http://localhost:3000 即可看到首页公司卡片网格。

### 5.2 页面一览

| 页面 | 地址 | 功能 |
|---|---|---|
| 首页 | `/` | 公司卡片网格，显示各公司 AI 岗位数 |
| 公司详情 | `/company?name=字节跳动` | 岗位列表 + 按类型/技术栈/领域筛选 |
| JD 详情 | `/jobs?id=xxx` | 左原文 + 右备考面板（项目要求/技术栈/5 道面试题） |
| 搜索 | `/search?q=RAG` | 跨公司按技术栈搜索 |

---

## 六、第 4 步：部署上线（可选，两套方案）

### 方案 A：免费 Vercel（推荐，前端）

1. 把项目推到 GitHub 仓库
2. 到 https://vercel.com → New Project → 选择仓库 → Framework 选 **Next.js**
3. 环境变量填 `NEXT_PUBLIC_SUPABASE_URL`、`NEXT_PUBLIC_SUPABASE_ANON_KEY`
4. Deploy，完成。每次推送代码自动重新部署

### 方案 B：GitHub Actions 定时爬取（后端自动化）

1. 把代码推到 GitHub 仓库
2. 仓库 **Settings → Secrets and variables → Actions**，逐个添加：
   `SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`、`OPENAI_API_KEY`（可选 `OPENAI_BASE_URL`、`LLM_MODEL`、`CONTACT_EMAIL`、`FEISHU_WEBHOOK`/`SLACK_WEBHOOK`）
3. 等每天 06:00（北京时间）自动运行；也可以在 **Actions → daily-crawl → Run workflow** 手动触发

> 想先在本地跑定时任务（不依赖 GitHub），用：`python backend/main.py --schedule`

---

## 七、如何扩展公司清单（PRD 要求写清楚）

### 情况 A：该公司用 mokahr 招聘系统（大量独角兽用）

在 `backend/crawler/adapters/mokahr.py` 底部照抄一段配置：

```python
@register("公司id")
class 新公司Spider(MokahrSpider):
    """公司名"""
    company: str = "公司名"
    company_category: str = "大模型独角兽"
    org_path: str = "/campus-recruitment/公司slug/数字id"   # 从招聘页地址栏复制
```

### 情况 B：官网自建招聘频道

在 `backend/crawler/adapters/official_site.py` 底部调用一次工厂函数：

```python
make_official_site_spider(
    adapter_id="新公司id",
    company="公司名",
    company_category="大模型独角兽",
    start_url="https://www.xxx.com/careers",
    # 下面两项可选，页面结构特殊时再改
    link_pattern="a[href*='/job']",
    detail_selector=".job-detail",
)
```

### 情况 C：无法爬取（robots 禁止 / 无招聘页）

用**手动导入**：编辑 `data/manual_jobs.json`（格式见 `backend/crawler/adapters/manual.py` 顶部注释），把 JD 文本粘进去，爬虫会自动读取。程序也会在 robots 禁止时**自动降级**到该模式并给出提示。

---

## 八、常见问题排查

| 现象 | 原因 | 解决 |
|---|---|---|
| `robots.txt 不可用，保守跳过` | 域名解析失败或网络问题 | 检查网络，或给 `.env` 配代理；不影响其它公司 |
| `XX 列表为空或解析失败` | 网站改版，选择器失效 | 用浏览器打开该公司招聘页，按 F12 查看岗位链接的 class/href 特征，更新对应适配器顶部的 `LINK_PATTERN` / 选择器常量 |
| `LLM 调用失败` | Key 错误 / 余额不足 / 网络 | 检查 `.env` 三项；国内网络建议用 DeepSeek/硅基流动等兼容接口 |
| `结构化成功 0` | JD 尚未入库或 hash 未变 | 先跑 `python backend/main.py --no-enrich` 爬取入库，再跑 `--enrich-only` |
| 首页「尚未配置数据库」 | 前端 `.env.local` 缺失 | 按第五节配置后重新 `npm run build` |
| 前端空白/500 | Node 版本过旧 | 安装 Node 20+ 后重装 `node_modules` |

---

## 九、合规与数据说明

- **只访问企业官方招聘域名**，每次请求前检查 `robots.txt`，遵守 `Disallow` 与 `Crawl-delay`
- 请求间隔 3~5 秒随机，单域名每日 ≤ 200 条，User-Agent 含项目名与联系方式
- 仅采集岗位公开描述，不采集任何候选人个人信息
- JD 原文版权归各企业所有，本平台仅做结构化整理与学习用途（前端页脚已声明）
- 本项目仅供学习交流，请勿用于商业牟利

## 十、技术栈

Python 3.11 · Playwright · BeautifulSoup · OpenAI SDK（兼容 DeepSeek 等）· Supabase(Postgres) · Next.js 14 · Tailwind CSS · GitHub Actions
