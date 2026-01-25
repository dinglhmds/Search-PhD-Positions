import asyncio
import os
import json
import logging
from pathlib import Path
from typing import List, Set
import sys

from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# 加载 .env（仅在本地开发时需要）
from dotenv import load_dotenv
load_dotenv()

# ==============================
# 导入你的 Agent 模块
# ==============================
try:
    from src.agents.search_agent import SearchAgent
    from src.agents.planner_agent import PlannerAgent
    from src.agents.crawler_agent import CrawlerAgent
    from src.agents.parser_agent import ParserAgent
except ImportError:
    print("Warning: Agent modules not found. Ensure src/agents/ exists.")
    pass

# ==============================
# 从环境变量读取配置
# ==============================
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
LLM_API_KEY = os.getenv("LLM_API_KEY")

# 检查必要密钥是否存在（避免运行时才发现问题）
if not SEARCH_API_KEY:
    raise ValueError("Missing SEARCH_API_KEY in environment variables.")
if not LLM_API_KEY:
    raise ValueError("Missing LLM_API_KEY in environment variables.")

RUNS_DIR = Path(os.getenv("RUNS_DIR", "./runs"))
RUNS_DIR.mkdir(exist_ok=True)

# ==============================
# 日志配置（不变）
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="University Faculty Scraper")

# ==============================
# 辅助函数：处理打包后的静态资源路径
# ==============================
def get_resource_path(relative_path: str) -> Path:
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path

static_dir = get_resource_path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
else:
    logger.warning(f"Static directory not found: {static_dir}")


# ==============================
# 辅助函数：数据统计与读取
# ==============================
def get_existing_universities():
    """扫描 runs 目录，返回所有已解析的学校统计信息"""
    universities = []
    # 查找所有 _parsed.json 结尾的文件
    for file_path in RUNS_DIR.glob("*_parsed.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 从文件名提取 uni 简称 (e.g. "GMU_parsed.json" -> "GMU")
            uni_name = file_path.name.replace("_parsed.json", "")
            
            faculty_list = data.get("faculty", [])
            
            # 统计逻辑
            total_members = len(faculty_list)
            
            # Unique Titles (去重后的职称数量，代表职称多样性/大牛分布)
            titles = set(p.get("title", "").strip() for p in faculty_list if p.get("title"))
            unique_titles_count = len(titles)
            
            # Research Areas (去重后的研究领域数量)
            areas = set()
            for p in faculty_list:
                for area in p.get("research_areas", []):
                    areas.add(area.strip())
            total_areas = len(areas)

            universities.append({
                "uni": uni_name,
                "count": total_members,
                "titles_count": unique_titles_count,
                "areas_count": total_areas,
                "path": f"/uni/{uni_name}"
            })
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
    
    # 按名称排序
    universities.sort(key=lambda x: x["uni"])
    return universities

# ==============================
# HTML 模板生成器
# ==============================

def get_dashboard_html(universities, error=None, loading_uni=None):
    """生成首页 Dashboard HTML"""
    cards_html = ""
    for u in universities:
        cards_html += f'''
        <div class="uni-card" onclick="location.href='{u['path']}'" data-uni="{u['uni'].lower()}">
            <div class="uni-header">
                <h3>🏫 {u['uni']}</h3>
                <span class="badge">已缓存</span>
            </div>
            <div class="stats-grid">
                <div class="stat-item">
                    <span class="stat-val">{u['count']}</span>
                    <span class="stat-label">Faculty Members</span>
                </div>
                <div class="stat-item">
                    <span class="stat-val">{u['titles_count']}</span>
                    <span class="stat-label">Unique Titles</span>
                </div>
                <div class="stat-item">
                    <span class="stat-val">{u['areas_count']}</span>
                    <span class="stat-label">Research Areas</span>
                </div>
            </div>
        </div>
        '''

    loading_html = ""
    if loading_uni:
        loading_html = f'''
        <div class="overlay">
            <div class="loader-box">
                <div class="spinner"></div>
                <h2>🔄 正在抓取 {loading_uni} ...</h2>
                <p>正在执行：搜索 -> 爬取 -> 解析</p>
                <p>请耐心等待 30-60 秒</p>
            </div>
        </div>
        '''

    error_html = f'<div class="status error">{error}</div>' if error else ""

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Faculty Scraper Dashboard</title>
    <link rel="icon" href="/static/favicon.ico" type="image/x-icon">
    <style>
        :root {{ --primary: #2563eb; --bg: #f3f4f6; --card-bg: #ffffff; --text: #1f2937; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); padding: 40px; margin: 0; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        h1 {{ text-align: center; color: #111827; margin-bottom: 40px; font-size: 2.5rem; }}
        
        /* 搜索区 */
        .search-section {{ text-align: center; margin-bottom: 50px; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        .search-box {{ display: flex; justify-content: center; gap: 10px; max-width: 600px; margin: 0 auto; }}
        input[type="text"] {{ flex: 1; padding: 15px; border: 2px solid #e5e7eb; border-radius: 8px; font-size: 1.1rem; outline: none; transition: border-color 0.2s; }}
        input[type="text"]:focus {{ border-color: var(--primary); }}
        button {{ padding: 15px 30px; background: var(--primary); color: white; border: none; border-radius: 8px; font-size: 1.1rem; cursor: pointer; font-weight: 600; transition: background 0.2s; }}
        button:hover {{ background: #1d4ed8; }}

        /* 网格布局 */
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 25px; }}
        
        /* 卡片样式 */
        .uni-card {{ background: var(--card-bg); border-radius: 12px; padding: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; border: 1px solid #e5e7eb; }}
        .uni-card:hover {{ transform: translateY(-5px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-color: var(--primary); }}
        
        .uni-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #f3f4f6; padding-bottom: 15px; }}
        .uni-header h3 {{ margin: 0; font-size: 1.5rem; color: #111827; }}
        .badge {{ background: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }}
        
        .stats-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; text-align: center; }}
        .stat-item {{ display: flex; flex-direction: column; }}
        .stat-val {{ font-size: 1.25rem; font-weight: bold; color: var(--primary); }}
        .stat-label {{ font-size: 0.75rem; color: #6b7280; margin-top: 4px; }}

        /* 状态与加载 */
        .status.error {{ background: #fee2e2; color: #991b1b; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: center; }}
        
        .overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; justify-content: center; align-items: center; z-index: 1000; }}
        .loader-box {{ background: white; padding: 40px; border-radius: 16px; text-align: center; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }}
        .spinner {{ border: 4px solid #f3f3f3; border-top: 4px solid var(--primary); border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 20px; }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}

    </style>
</head>
<body>
    {loading_html}
    <div class="container">
        <h1>🎓 University Faculty Scraper</h1>
        
        <div class="search-section">
            <form method="POST" action="/scrape" id="searchForm">
                <div class="search-box">
                    <input type="text" id="uniInput" name="uni" placeholder="输入学校名称" required onkeyup="filterCards()">
                    <button type="submit" id="actionBtn">搜索 / 抓取</button>
                </div>
                <div style="margin-top: 10px; color: #6b7280; font-size: 0.9rem;">
                    💡 提示：如果下方已有卡片，直接点击即可；如果找不到，点击按钮开始抓取。
                </div>
            </form>
        </div>

        {error_html}

        <div class="grid" id="cardGrid">
            {cards_html}
        </div>
    </div>

    <script>
        function filterCards() {{
            const input = document.getElementById('uniInput').value.toLowerCase();
            const cards = document.getElementsByClassName('uni-card');
            let found = false;

            for (let card of cards) {{
                const uniName = card.getAttribute('data-uni');
                if (uniName.includes(input)) {{
                    card.style.display = "block";
                    found = true;
                }} else {{
                    card.style.display = "none";
                }}
            }}

            const btn = document.getElementById('actionBtn');
            if (found && input.length > 0) {{
                btn.innerText = "添加 / 重新抓取";
                btn.style.background = "#4b5563"; // 灰色，表示主要是筛选
            }} else if (input.length > 0) {{
                btn.innerText = "未找到，开始抓取 " + input.toUpperCase();
                btn.style.background = "#2563eb"; // 蓝色，表示需要执行
            }} else {{
                btn.innerText = "搜索 / 抓取";
                btn.style.background = "#2563eb";
            }}
        }}
    </script>
</body>
</html>
    """

def get_detail_html(uni, faculty_data):
    """生成详情页 HTML"""
    faculty_html = ""
    for prof in faculty_data.get("faculty", []):
        name = prof.get("name", "N/A")
        title = prof.get("title", "N/A")
        email = prof.get("email", "N/A")
        areas = ", ".join(prof.get("research_areas", [])) or "未提供"
        
        # 用于前端搜索的组合字符串
        search_text = f"{name} {areas}".lower()
        
        faculty_html += f'''
        <div class="card" data-search="{search_text}">
            <div class="card-header">
                <h3>{name}</h3>
                <span class="prof-title">{title}</span>
            </div>
            <div class="card-body">
                <p class="email">📧 {email}</p>
                <p class="areas">🔬 {areas}</p>
            </div>
        </div>'''

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{uni} - Faculty Details</title>
    <link rel="icon" href="/static/favicon.ico" type="image/x-icon">
    <style>
        :root {{ --primary: #2563eb; --bg: #f5f7fa; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: var(--bg); padding: 0; margin: 0; }}
        
        /* 顶部导航条 */
        header {{ background: white; padding: 15px 40px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }}
        .nav-left {{ display: flex; align-items: center; gap: 20px; }}
        .back-btn {{ text-decoration: none; color: #4b5563; font-weight: 600; display: flex; align-items: center; gap: 5px; padding: 8px 16px; border-radius: 6px; background: #f3f4f6; transition: 0.2s; }}
        .back-btn:hover {{ background: #e5e7eb; color: #111827; }}
        h2 {{ margin: 0; color: #111827; }}

        /* 搜索框 */
        .filter-box {{ position: relative; width: 400px; }}
        .filter-box input {{ width: 100%; padding: 10px 15px; border: 1px solid #d1d5db; border-radius: 20px; outline: none; transition: 0.2s; }}
        .filter-box input:focus {{ border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1); }}

        .container {{ max-width: 1200px; margin: 40px auto; padding: 0 20px; }}
        
        .cards-grid {{ display: grid; gap: 20px; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); }}
        
        .card {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid var(--primary); transition: transform 0.2s; }}
        .card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        
        .card-header h3 {{ margin: 0 0 5px 0; color: #1f2937; }}
        .prof-title {{ font-size: 0.9rem; color: #6b7280; font-style: italic; background: #f3f4f6; padding: 2px 8px; border-radius: 4px; }}
        
        .card-body {{ margin-top: 15px; }}
        .email {{ color: #4b5563; font-size: 0.95rem; margin-bottom: 5px; }}
        .areas {{ color: #1f2937; font-size: 0.95rem; line-height: 1.4; }}
        
        .no-result {{ text-align: center; padding: 40px; color: #6b7280; display: none; }}
    </style>
</head>
<body>
    <header>
        <div class="nav-left">
            <a href="/" class="back-btn">⬅ 返回首页</a>
            <h2>🏫 {uni} Faculty List</h2>
        </div>
        <div class="filter-box">
            <input type="text" id="filterInput" placeholder="🔍 搜索导师姓名或研究方向..." onkeyup="filterFaculty()">
        </div>
    </header>

    <div class="container">
        <div id="stats-bar" style="margin-bottom: 20px; color: #6b7280;">
            共找到 {len(faculty_data.get('faculty', []))} 位导师
        </div>
        
        <div class="cards-grid" id="facultyGrid">
            {faculty_html}
        </div>
        <div id="noResult" class="no-result">未找到匹配的导师信息</div>
    </div>

    <script>
        function filterFaculty() {{
            const input = document.getElementById('filterInput').value.toLowerCase();
            const cards = document.getElementsByClassName('card');
            let visibleCount = 0;

            for (let card of cards) {{
                const text = card.getAttribute('data-search');
                if (text.includes(input)) {{
                    card.style.display = "";
                    visibleCount++;
                }} else {{
                    card.style.display = "none";
                }}
            }}

            const noResult = document.getElementById('noResult');
            noResult.style.display = visibleCount === 0 ? "block" : "none";
        }}
    </script>
</body>
</html>
    """

# ==============================
# 路由逻辑
# ==============================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """首页：展示所有已存在的学校卡片"""
    unis = get_existing_universities()
    return HTMLResponse(get_dashboard_html(unis))

@app.get("/uni/{uni_name}", response_class=HTMLResponse)
async def uni_detail(uni_name: str):
    """详情页：展示特定学校的导师列表"""
    json_path = RUNS_DIR / f"{uni_name}_parsed.json"
    
    if not json_path.exists():
        # 如果文件不存在，重定向回首页并提示错误（或者可以触发自动抓取，这里选择显式错误）
        unis = get_existing_universities()
        return HTMLResponse(get_dashboard_html(unis, error=f"找不到 {uni_name} 的数据，请先在首页进行抓取。"))

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return HTMLResponse(get_detail_html(uni_name, data))
    except Exception as e:
        unis = get_existing_universities()
        return HTMLResponse(get_dashboard_html(unis, error=f"读取数据出错: {e}"))

@app.post("/scrape", response_class=HTMLResponse)
async def run_pipeline(uni: str = Form(...)):
    """处理抓取请求"""
    uni = uni.strip()
    if not uni:
        unis = get_existing_universities()
        return HTMLResponse(get_dashboard_html(unis, error="请输入大学名称"))

    md_path = RUNS_DIR / f"{uni}.md"
    json_path = RUNS_DIR / f"{uni}_parsed.json"

    # 如果已存在，直接跳转到详情页
    if json_path.exists():
        logger.info(f"Data for {uni} already exists. Redirecting.")
        return RedirectResponse(url=f"/uni/{uni}", status_code=303)

    # 如果不存在，执行 Pipeline
    try:
        logger.info(f"Starting pipeline for {uni}...")
        
        # --- Pipeline Start ---
        
        # Step 1: Normalize (获取正确域名)
        planner = PlannerAgent(api_key=LLM_API_KEY)
        uni_info = await planner.normalize_university(uni)
        logger.info(f"Normalized: {uni_info}")

        # Step 2: Search (找 URL)
        searcher = SearchAgent(serpapi_key=SEARCH_API_KEY, top_k=10)
        results = await searcher.search_faculty_pages(uni_info["domain"])
        if not results:
            unis = get_existing_universities()
            return HTMLResponse(get_dashboard_html(unis, error=f"未找到 {uni} 的师资页面"))
        
        target_url = results[0]['url']
        logger.info(f"Target URL: {target_url}")

        # Step 3: Crawl (爬取内容)
        async with CrawlerAgent() as crawler:
            await crawler.crawl_faculty(target_url, save_md=True, md_path=str(md_path))
        
        if not md_path.exists():
             raise Exception("Markdown file was not generated.")

        # Step 4: Parse (解析数据)
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        parser = ParserAgent(api_key=LLM_API_KEY)
        parsed_result = parser.parse(content)

        # Save JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(parsed_result, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Pipeline finished for {uni}")
        
        # --- Pipeline End ---

        # 成功后跳转到详情页
        return RedirectResponse(url=f"/uni/{uni}", status_code=303)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        unis = get_existing_universities()
        return HTMLResponse(get_dashboard_html(unis, error=f"抓取失败: {str(e)[:200]}"))
    
@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.ico")

# ==============================
# 启动
# ==============================
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 App running at http://localhost:{port}")
    uvicorn.run(app, host=host, port=port)