# Search-PhD-Positions

这是一个自动化博士申请系统的Python应用，专为帮助博士申请者寻找和联系潜在导师而设计。系统通过AI技术自动搜索、解析大学导师信息，并生成个性化的联系邮件。

## 功能特性

- **自动化导师搜索**: 使用AI驱动的搜索引擎自动查找大学导师页面
- **信息提取**: 从网页提取导师的姓名、职称、研究领域、邮箱和主页链接
- **大学标准化**: 使用YAML配置或AI模型标准化大学名称和域名
- **个性化邮件生成**: 基于申请人背景生成个性化的联系邮件
- **Web界面**: 直观的Web界面用于浏览和管理目标导师
- **用户档案管理**: 保存和管理申请人个人档案信息

## 技术架构

系统采用模块化代理架构：
- **SearchAgent**: 使用SerpApi进行Google搜索
- **PlannerAgent**: 大学名称标准化
- **CrawlerAgent**: 异步网页爬取
- **ParserAgent**: AI驱动的内容解析
- **EmailAgent**: 智能邮件生成
- **FastAPI**: Web框架和API接口

## 环境配置

### 1. 克隆项目

```bash
git clone <repository-url>
cd PhD-App
```

### 2. 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

创建 `.env` 文件并添加以下配置：

```env
SEARCH_API_KEY=your_serpapi_key_here
LLM_API_KEY=your_siliconflow_api_key_here
RUNS_DIR=./runs
```

### 5. API服务配置

- **SerpApi**: 获取Google搜索API密钥，用于搜索导师页面
- **SiliconFlow**: 获取AI模型API密钥，用于解析和生成内容

### 6. 启动应用

```bash
python main.py
```

应用将运行在 `http://127.0.0.1:8000`

## 使用方法

1. 在主页输入大学名称（如"Stanford", "MIT", "UCB"等）
2. 系统会自动搜索、爬取、解析并展示该大学的导师信息
3. 浏览导师列表，点击查看详细信息或收藏
4. 在"个人档案"页面填写申请人信息
5. 点击导师信息旁的"写信"按钮生成个性化邮件

## 文件结构

```
PhD-App/
├── main.py              # 主应用文件
├── requirements.txt     # 依赖包列表
├── .env                 # 环境变量配置
├── configs/
│   └── universities.yaml # 大学名称映射配置
├── runs/               # 运行结果存储目录
├── src/
│   └── agents/         # AI代理模块
│       ├── search_agent.py    # 搜索代理
│       ├── planner_agent.py   # 规划代理
│       ├── crawler_agent.py   # 爬取代理
│       ├── parser_agent.py    # 解析代理
│       └── email_agent.py     # 邮件代理
├── static/             # 静态资源
└── venv/               # 虚拟环境
```

## 注意事项

- 需要有效的SerpApi密钥用于Google搜索
- 需要有效的SiliconFlow API密钥用于AI服务
- 遵守目标网站的robots.txt和使用条款
- 搜索和爬取操作可能需要几分钟时间，具体取决于网站响应速度
