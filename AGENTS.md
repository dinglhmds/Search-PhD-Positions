# PhD-App — Agent 开发指南

> 本文件面向 AI Coding Agent。阅读前请确认你已了解：项目使用 Python 3.11，所有注释和 UI 文案以中文为主，处理的数据为英文学术内容。

---

## 1. 项目概述

PhD-App 是一个自动化博士申请辅助系统的 Python Web 应用，帮助申请者：
- 自动搜索目标院校的计算机系导师页面
- 使用 AI 解析并提取导师姓名、职称、研究方向、邮箱、个人主页链接
- 在 Web 界面中浏览、搜索、收藏导师
- 基于申请者个人档案，自动生成个性化英文套磁信（Cold Email）

核心工作流：输入大学名称 → 标准化校名 → Google 搜索导师页 → 异步爬取 → LLM 解析 → 生成 JSON → Web 展示 → 生成邮件。

---

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| 数据校验 | Pydantic v2 |
| 环境配置 | `python-dotenv` + `.env` 文件 |
| 包管理 | `uv` + `pyproject.toml` |
| 异步 HTTP | `aiohttp` |
| 网页爬取 | `Crawl4AI` (`AsyncWebCrawler`) |
| LLM 调用 | SiliconFlow API（OpenAI 兼容接口） |
| LLM 客户端 | `openai` 官方库 + `langchain-community` ChatOpenAI |
| 搜索 API | SerpApi（Google 搜索） |
| 配置数据 | PyYAML (`configs/universities.yaml`) |
| 前端 | 纯 HTML/CSS/JS，全部以 f-string 嵌入 `main.py`，无独立前端构建工具 |
| 持久化 | 本地文件系统（`runs/` 目录存放 `.md` 和 `_parsed.json`），无数据库 |

---

## 3. 代码组织结构

```
PhD-App/
├── main.py                      # 唯一主入口：FastAPI 应用、路由、Pydantic Models、HTML 模板
├── pyproject.toml               # 项目配置与依赖（uv 管理）
├── .python-version              # Python 版本锁定（3.11）
├── .env                         # 环境变量（API Key、路径），从未提交到 Git
├── configs/
│   └── universities.yaml        # 大学官方名称、域名、别名映射（800+ 条）
├── src/
│   ├── __init__.py              # 空文件
│   └── agents/
│       ├── __init__.py          # 导出所有 Agent 类
│       ├── search_agent.py      # SearchAgent：通过 SerpApi 执行 Google 搜索
│       ├── planner_agent.py     # PlannerAgent：标准化大学名称 / 获取域名
│       ├── crawler_agent.py     # CrawlerAgent：基于 Crawl4AI 异步爬取网页并保存 Markdown
│       ├── parser_agent.py      # ParserAgent：调用 LLM 并行解析 Markdown，提取导师信息
│       └── email_agent.py       # EmailAgent：调用 LLM 根据申请者档案和导师信息生成套磁信
├── runs/                        # 运行时输出目录：{uni}.md（原始 Markdown）和 {uni}_parsed.json（解析结果）
├── runs_old/                    # 历史归档数据
├── static/                      # 静态资源：favicon、图标、about.txt
├── test/                        # 实验脚本、旧版本 Web 应用、静态页面原型
└── .venv/                       # Python 虚拟环境（uv 自动创建）
```

### 3.1 模块职责详解

- **`main.py`**（660+ 行）
  - 创建 `FastAPI` 实例，挂载 `/static` 静态文件
  - 定义 Pydantic 模型：`ApplicantProfile`、`ProfInfo`、`GenerateEmailRequest`
  - 提供 `get_base_layout()` 生成包含侧边栏、Modal、通用 JS 的基础页面
  - 路由：`/`（首页/搜索）、`/uni/{uni_name}`（导师列表）、`/targets`（意向导师）、`/profile`（个人档案）
  - 路由：`POST /scrape`（执行完整抓取流水线）、`POST /api/generate-email`（生成邮件）
  - 前端状态（收藏、档案）完全存储在浏览器 `localStorage`，后端无用户状态

- **`src/agents/search_agent.py`**
  - `SearchAgent(serpapi_key, top_k)`
  - `search_faculty_pages(domain)` 构造查询 `site:{domain} "computer science" ("faculty" OR "professor"...)`
  - 返回 `List[Dict]`，字段：`title`, `url`, `snippet`

- **`src/agents/planner_agent.py`**
  - `PlannerAgent(api_key, model, yaml_path)`
  - 优先查询本地 `universities.yaml` 映射；未命中则调用 SiliconFlow LLM 返回 `{"standard_name": ..., "domain": ...}`
  - 失败时有降级策略：猜测 `xxx.edu`

- **`src/agents/crawler_agent.py`**
  - `CrawlerAgent` 为异步上下文管理器（`__aenter__` / `__aexit__`）
  - `crawl_faculty(base_url, save_md, md_path)` 调用 `crawl4ai.AsyncWebCrawler.arun()`
  - 将结果 Markdown 写入文件

- **`src/agents/parser_agent.py`**
  - `ParserAgent(api_key, model_name, max_workers)`
  - 将 Markdown 按 `max_chunk_size=8000` 字符分块
  - 使用 `ThreadPoolExecutor`（最多 8 线程）并行调用 LLM 解析每个分块
  - LLM Prompt 要求提取：`name`, `title`, `research_areas`（列表）, `email`, `link`
  - 输出必须为 JSON；失败时回退到正则提取（`_fallback_parse`）
  - 最终按 `name` 去重

- **`src/agents/email_agent.py`**
  - `EmailAgent(api_key, model)`
  - `generate_email(applicant_profile, prof_info)` 调用 SiliconFlow 生成英文套磁信
  - Prompt 要求：300 词以内、学术英语、展示背景与教授研究方向的 Fit、包含 Subject

---

## 4. 构建与运行命令

### 4.1 环境准备

```bash
# 安装依赖并创建虚拟环境（.venv/）
uv sync

# 若仅需生产依赖
uv sync --no-dev
```

### 4.2 配置环境变量

在项目根目录创建 `.env`：

```env
SEARCH_API_KEY=your_serpapi_key_here
LLM_API_KEY=your_siliconflow_api_key_here
RUNS_DIR=./runs
```

- `SEARCH_API_KEY`：SerpApi 密钥，用于 Google 搜索
- `LLM_API_KEY`：SiliconFlow 密钥，用于 Qwen 模型调用
- `RUNS_DIR`：运行结果存放目录，默认为 `./runs`

### 4.3 启动应用

```bash
uv run python main.py
```

- 服务运行在 `http://127.0.0.1:8000`
- 生产环境无额外部署配置，直接通过 Uvicorn 启动

---

## 5. 数据流水线与关键数据格式

### 5.1 抓取流水线（`POST /scrape`）

1. 接收表单字段 `uni`（大学名称或别名）
2. 若 `runs/{uni}_parsed.json` 已存在，直接跳转详情页（幂等/缓存策略）
3. `PlannerAgent.normalize_university(uni)` → 得到标准名和域名
4. `SearchAgent.search_faculty_pages(domain)` → 获取 Top 5 搜索结果
5. 取第一条结果，`CrawlerAgent` 爬取并保存为 `runs/{uni}.md`
6. `ParserAgent.parse(md_content)` → 生成 `{"faculty": [...]}`
7. 写入 `runs/{uni}_parsed.json`，跳转 `/uni/{uni}`

### 5.2 解析结果 JSON 格式

```json
{
  "faculty": [
    {
      "name": "Prof. Name",
      "title": "Assistant Professor",
      "research_areas": ["machine learning", "computer vision"],
      "email": "name@university.edu",
      "link": "https://www.university.edu/~name"
    }
  ]
}
```

字段说明：
- `name`：导师姓名
- `title`：职称（可能为英文原文或中文“未提供”）
- `research_areas`：字符串列表；解析失败时可能为空列表 `[]`
- `email`：邮箱；无则为 `"未提供"`
- `link`：个人主页 URL；无则为 `"未提供"`

### 5.3 已抓取院校索引

`main.py` 中的 `get_existing_universities()` 扫描 `RUNS_DIR` 下所有 `*_parsed.json` 文件，按文件名排序生成院校卡片列表。

---

## 6. 代码风格与开发约定

### 6.1 语言与注释
- 所有源代码注释、Docstring、UI 文案使用**中文**
- 代码标识符（类名、函数名、变量名）使用英文
- 打印日志和错误信息混合使用中英文

### 6.2 Agent 模块模式
- 每个 Agent 为独立 Python 类，放在 `src/agents/` 下
- Agent 的 `__init__` 接收 `api_key` 等配置，部分提供默认模型名
- 多个 Agent 文件底部包含 `async def main()` + `if __name__ == "__main__": asyncio.run(main())` 用于**手动快速测试**
- **注意**：部分 Agent 的 `__main__` 区块和 `test/main.py` 中**硬编码了 API 密钥**，修改或提交代码前需清理

### 6.3 前端实现方式
- 无 Jinja2、无 React/Vue
- 所有 HTML 页面由 `main.py` 中的 `get_base_layout()` 和各个路由 handler 通过 Python f-string 拼接生成
- CSS 以 `<style>` 标签内嵌在基础布局中
- JavaScript 以 `<script>` 标签内嵌，处理：localStorage 读写、Modal 弹窗、收藏增删、邮件生成异步请求、导师列表前端筛选

### 6.4 异步与并发
- Web 层使用 FastAPI 的 `async def` 路由
- `SearchAgent` 和 `CrawlerAgent` 使用 `async/await`
- `ParserAgent` 内部使用**同步**的 `langchain_community.chat_models.ChatOpenAI.invoke()`，并发通过 `ThreadPoolExecutor` 实现，而非 `asyncio`

---

## 7. 测试策略

### 7.1 现状
- **无单元测试框架**：项目中没有 `pytest`、`unittest` 或 `tox`
- **无 CI/CD**：没有 `.github/workflows/` 或类似配置

### 7.2 现有测试手段
- **Agent 独立测试**：每个 Agent 文件底部的 `__main__` 块可单独运行验证功能
- **集成测试脚本**：`test/main.py` 提供完整流水线测试，从 `PlannerAgent` → `SearchAgent` → `CrawlerAgent` → `ParserAgent`
- **手动 Web 测试**：启动 `main.py` 后在浏览器中操作
- **静态原型**：`test/` 目录下 `web_app_v0.py` / `v1.py` / `v2.py` 等为历史迭代版本，仅作参考

### 7.3 建议新增测试时的约定
- 如需添加正式测试，建议在 `test/` 目录下创建 `test_*.py` 文件
- 对 LLM 调用部分使用 `unittest.mock` patch `ChatOpenAI.invoke` 或 `openai.OpenAI.chat.completions.create`
- 对 SerpApi 调用 patch `aiohttp.ClientSession.get`

---

## 8. 安全注意事项

### 8.1 密钥管理（已知风险）
- **`.env`** 已被 `.gitignore` 排除，符合安全要求
- ~~**硬编码密钥**：以下文件中存在硬编码的 API 密钥，修改或提交前必须移除或环境变量化~~（已清理）
  - `src/agents/search_agent.py`、`planner_agent.py`、`parser_agent.py` 的 `__main__` 测试块
  - `test/main.py`、`test/web_app.py`、`test/parser_agent_old.py`
  - 全部改为从环境变量读取，缺失时提示并退出

### 8.2 Web 安全
- 应用**无身份认证**、**无会话管理**，任何能访问 `127.0.0.1:8000` 的用户均可触发抓取和邮件生成
- `POST /scrape` 接收原始用户输入 `uni`，直接拼接到文件路径和搜索查询中，需防范路径遍历（当前通过 `RUNS_DIR` 限制在目标目录内，但仍建议校验输入）
- 前端通过 `localStorage` 保存收藏和档案，数据仅存于客户端

### 8.3 外部依赖
- 依赖第三方 API（SerpApi、SiliconFlow）的可用性和计费策略
- 爬取操作需遵守目标网站的 `robots.txt` 和使用条款

---

## 9. 常见修改场景指引

| 场景 | 应该修改的文件 |
|------|--------------|
| 新增大学别名或修正域名 | `configs/universities.yaml` |
| 调整搜索查询语句 | `src/agents/search_agent.py` |
| 更换 LLM 模型 | 各 Agent 的 `model` 默认参数（`planner_agent.py`, `parser_agent.py`, `email_agent.py`） |
| 修改解析字段或 Prompt | `src/agents/parser_agent.py` 中的 `_parse_chunk` prompt |
| 调整邮件生成风格 | `src/agents/email_agent.py` 中的 `system_prompt` / `user_prompt` |
| 修改页面样式或布局 | `main.py` 中的 `get_base_layout()` 或各路由 handler |
| 新增前端交互功能 | `main.py` 中的内嵌 `<script>` 部分 |
| 调整并发线程数 | `parser_agent.py` 中的 `max_workers` |

---

## 10. 快速开始（最小可运行步骤）

1. 确认 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/) 已安装
2. `uv sync`
3. 创建 `.env` 并填入有效的 `SEARCH_API_KEY` 和 `LLM_API_KEY`
4. `uv run python main.py`
5. 浏览器访问 `http://127.0.0.1:8000`
6. 在首页输入大学名称（如 `Columbia`、`MIT`、`UMD`），点击“开始抓取”
7. 等待流水线完成后浏览导师列表，填写个人档案，生成邮件

---

*本文件基于项目实际代码生成。如需修改项目结构、技术栈或流水线逻辑，请同步更新此文档。*
