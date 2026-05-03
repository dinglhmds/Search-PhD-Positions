import os
import json
import logging
from pathlib import Path
from typing import List, Optional, Union
import sys

from fastapi import FastAPI, Request, Form, Body
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

# 加载 .env
from dotenv import load_dotenv
load_dotenv()

# ==============================
# 导入 Agent 模块
# ==============================
from src.agents.search_agent import SearchAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.crawler_agent import CrawlerAgent
from src.agents.parser_agent import ParserAgent
from src.agents.email_agent import EmailAgent

# ==============================
# 配置
# ==============================
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
LLM_API_KEY = os.getenv("LLM_API_KEY")
RUNS_DIR = Path(os.getenv("RUNS_DIR", "./runs"))
RUNS_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="University Faculty Scraper Pro")

# 静态资源
def get_resource_path(relative_path: str) -> Path:
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path

static_dir = get_resource_path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Jinja2 模板
templates = Jinja2Templates(directory="templates")

# ==============================
# Pydantic Models
# ==============================
class ApplicantProfile(BaseModel):
    name: str = "Unknown"
    university: Optional[str] = "Unknown University"
    major: Optional[str] = "N/A"
    gpa: Optional[str] = ""
    language_score: Optional[str] = ""
    experience: Optional[str] = ""
    intent: Optional[str] = "PhD Application"

class ProfInfo(BaseModel):
    name: str
    email: Optional[str] = None
    research_areas: Optional[Union[List[str], str]] = None
    uni_name: str
    title: Optional[str] = None
    link: Optional[str] = None

class GenerateEmailRequest(BaseModel):
    applicant: ApplicantProfile
    professor: ProfInfo

# ==============================
# 数据读取
# ==============================
def get_existing_universities():
    universities = []
    for file_path in RUNS_DIR.glob("*_parsed.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            uni_name = file_path.name.replace("_parsed.json", "")
            faculty_list = data.get("faculty", [])
            titles = set(p.get("title", "").strip() for p in faculty_list if p.get("title"))
            areas = set()
            for p in faculty_list:
                p_areas = p.get("research_areas", [])
                if isinstance(p_areas, list):
                    for area in p_areas: areas.add(area.strip())
                elif isinstance(p_areas, str):
                    areas.add(p_areas.strip())
            universities.append({
                "uni": uni_name,
                "count": len(faculty_list),
                "titles_count": len(titles),
                "areas_count": len(areas),
                "path": f"/uni/{uni_name}"
            })
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
    universities.sort(key=lambda x: x["uni"])
    return universities

# ==============================
# 路由
# ==============================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """首页"""
    unis = get_existing_universities()
    return templates.TemplateResponse(request, "index.html", {
        "title": "PhD-App",
        "active_tab": "search",
        "unis": unis
    })

@app.get("/uni/{uni_name}", response_class=HTMLResponse)
async def uni_detail(request: Request, uni_name: str):
    """详情页"""
    json_path = RUNS_DIR / f"{uni_name}_parsed.json"
    if not json_path.exists():
        return RedirectResponse("/")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    faculty_list = []
    js_data_map_lines = []

    for idx, prof in enumerate(data.get("faculty", [])):
        prof['uni_name'] = uni_name
        prof['id_hash'] = f"{uni_name}_{idx}"
        prof_json = json.dumps(prof)
        js_data_map_lines.append(f"window.profDataMap['{prof['id_hash']}'] = {prof_json};")

        areas_display = prof.get('research_areas', [])
        if isinstance(areas_display, list):
            areas_display_str = ", ".join(areas_display)
        else:
            areas_display_str = areas_display

        search_text = f"{prof.get('name', '')} {prof.get('title', '')} {areas_display_str}".lower()

        faculty_list.append({
            "name": prof.get('name', 'Unknown'),
            "title": prof.get('title', ''),
            "email": prof.get('email', ''),
            "areas_display": areas_display_str,
            "link": prof.get('link', ''),
            "id_hash": prof['id_hash'],
            "search_text": search_text
        })

    return templates.TemplateResponse(request, "uni_detail.html", {
        "title": f"{uni_name} - PhD-App",
        "active_tab": "search",
        "uni_name": uni_name,
        "faculty_list": faculty_list,
        "js_data_map_lines": js_data_map_lines
    })

@app.get("/targets", response_class=HTMLResponse)
async def targets_page(request: Request):
    return templates.TemplateResponse(request, "targets.html", {
        "title": "意向导师 - PhD-App",
        "active_tab": "targets"
    })

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    return templates.TemplateResponse(request, "profile.html", {
        "title": "个人档案 - PhD-App",
        "active_tab": "profile"
    })

@app.post("/scrape")
async def run_pipeline(uni: str = Form(...)):
    uni = uni.strip()
    json_path = RUNS_DIR / f"{uni}_parsed.json"
    if json_path.exists():
        return RedirectResponse(url=f"/uni/{uni}", status_code=303)

    try:
        planner = PlannerAgent(api_key=LLM_API_KEY)
        uni_info = await planner.normalize_university(uni)
        searcher = SearchAgent(serpapi_key=SEARCH_API_KEY, top_k=5)
        results = await searcher.search_faculty_pages(uni_info["domain"])
        if not results:
            raise Exception("No faculty page found")

        md_path = RUNS_DIR / f"{uni}.md"
        async with CrawlerAgent() as crawler:
            await crawler.crawl_faculty(results[0]['url'], save_md=True, md_path=str(md_path))

        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parser = ParserAgent(api_key=LLM_API_KEY)
        parsed = parser.parse(content)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        return RedirectResponse(url=f"/uni/{uni}", status_code=303)
    except Exception as e:
        logger.error(e)
        return HTMLResponse(f"<h3>❌ Error</h3><p>{e}</p>")

@app.post("/api/generate-email")
async def generate_email(request: GenerateEmailRequest):
    try:
        agent = EmailAgent(api_key=LLM_API_KEY)

        prof_data = request.professor.model_dump()
        areas = prof_data.get('research_areas')
        if isinstance(areas, list):
            prof_data['research_areas'] = ", ".join(areas)
        elif areas is None:
            prof_data['research_areas'] = "Not Specified"

        content = agent.generate_email(request.applicant.model_dump(), prof_data)
        return JSONResponse({"content": content})
    except Exception as e:
        logger.error(f"Generate email error: {e}")
        return JSONResponse({"content": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
