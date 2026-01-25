import asyncio
import os
import json
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# 假设你的 agent 模块路径正确（根据你的项目结构调整）
from src.agents.search_agent import SearchAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.crawler_agent import CrawlerAgent
from src.agents.parser_agent import ParserAgent

# ==============================
# 配置
# ==============================
SEARCH_API_KEY = "2899dff16c4f3007ab17f00bb2c87f87975d09165e13f295baf928e696dbdc83"
LLM_API_KEY = "sk-rcbqhobnnnytzvyvqxcfsiaejkaoxmyfsenxpakjbimtegrp"

# 创建 runs 目录
Path("./runs").mkdir(exist_ok=True)

# ==============================
# FastAPI App
# ==============================
app = FastAPI(title="University Faculty Scraper")

# 内联模板（避免外部文件依赖）
def get_html_template(faculty_data=None, uni="", error=None, is_loading=False):
    faculty_html = ""
    if faculty_data:
        for prof in faculty_data.get("faculty", []):
            name = prof.get("name", "N/A")
            title = prof.get("title", "N/A")
            email = prof.get("email", "N/A")
            areas = ", ".join(prof.get("research_areas", [])) or "未提供"
            faculty_html += f'''
            <div class="card">
                <h3>{name}</h3>
                <p class="title">{title}</p>
                <p class="email">📧 {email}</p>
                <p class="areas">🔬 {areas}</p>
            </div>'''

    status_msg = ""
    if is_loading:
        status_msg = f'<div class="status loading">🔄 正在处理 {uni}... 请稍候（可能需要 30-60 秒）</div>'
    elif error:
        status_msg = f'<div class="status error">❌ 错误: {error}</div>'
    elif faculty_data:
        count = len(faculty_data.get("faculty", []))
        status_msg = f'<div class="status success">✅ 成功解析 {count} 位教师信息！</div>'

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Faculty Scraper</title>
    <style>
        body {{ font-family: Arial, sans-serif; background: #f5f7fa; padding: 30px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ text-align: center; color: #2c3e50; margin-bottom: 30px; }}
        form {{ text-align: center; margin-bottom: 30px; }}
        input[type="text"] {{ padding: 12px; width: 300px; font-size: 1.1rem; border: 1px solid #ccc; border-radius: 6px; }}
        button {{ padding: 12px 24px; font-size: 1.1rem; background: #3498db; color: white; border: none; border-radius: 6px; cursor: pointer; margin-left: 10px; }}
        button:hover {{ background: #2980b9; }}
        .status {{ padding: 15px; margin: 20px 0; border-radius: 6px; text-align: center; font-weight: bold; }}
        .loading {{ background: #fff3cd; color: #856404; }}
        .error {{ background: #f8d7da; color: #721c24; }}
        .success {{ background: #d4edda; color: #155724; }}
        .cards {{ display: grid; gap: 20px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }}
        .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .card h3 {{ color: #2c3e50; margin-bottom: 8px; }}
        .title {{ color: #7f8c8d; font-style: italic; }}
        .email, .areas {{ margin-top: 8px; color: #34495e; }}
        footer {{ text-align: center; margin-top: 40px; color: #95a5a6; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎓 大学师资信息抓取器</h1>
        <form method="POST">
            <input type="text" name="uni" placeholder="请输入大学简称（如 GMU, UMD）" value="{uni}" required />
            <button type="submit">开始抓取</button>
        </form>

        {status_msg}

        <div class="cards">
            {faculty_html}
        </div>

        <footer>
            Powered by AI Agents | 数据保存于 ./runs/
        </footer>
    </div>
</body>
</html>
    """


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(get_html_template())


@app.post("/", response_class=HTMLResponse)
async def run_pipeline(request: Request, uni: str = Form(...)):
    uni = uni.strip()
    if not uni:
        return HTMLResponse(get_html_template(error="请输入大学名称"))

    md_path = f"./runs/{uni}.md"
    json_path = f"./runs/{uni}_parsed.json"

    # 如果已存在解析结果，直接返回（可选：加 force 参数跳过）
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return HTMLResponse(get_html_template(faculty_data=data, uni=uni))
        except Exception:
            pass  # 忽略，重新跑

    # 否则执行完整 pipeline
    try:
        # Step 1: Normalize
        planner = PlannerAgent(api_key=LLM_API_KEY)
        uni_info = await planner.normalize_university(uni)

        # Step 2: Search
        searcher = SearchAgent(serpapi_key=SEARCH_API_KEY, top_k=10)
        results = await searcher.search_faculty_pages(uni_info["domain"])
        if not results:
            return HTMLResponse(get_html_template(error=f"未找到 {uni} 的师资页面", uni=uni))

        # Step 3: Crawl
        target_url = results[0]['url']
        async with CrawlerAgent() as crawler:
            await crawler.crawl_faculty(target_url, save_md=True, md_path=md_path)

        # Step 4: Parse
        if not os.path.exists(md_path):
            return HTMLResponse(get_html_template(error="爬取失败：未生成 Markdown 文件", uni=uni))

        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        parser = ParserAgent(api_key=LLM_API_KEY)
        parsed_result = parser.parse(content)

        # Save JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(parsed_result, f, ensure_ascii=False, indent=2)

        return HTMLResponse(get_html_template(faculty_data=parsed_result, uni=uni))

    except Exception as e:
        error_msg = f"Pipeline 失败: {str(e)[:200]}"
        return HTMLResponse(get_html_template(error=error_msg, uni=uni))


# ==============================
# 启动说明
# ==============================
if __name__ == "__main__":
    print("🚀 启动 Faculty Scraper Web App...")
    print("访问 http://localhost:8000")
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)