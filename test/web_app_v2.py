import os
import json
import logging
from pathlib import Path
from typing import List, Optional, Union
import sys

from fastapi import FastAPI, Request, Form, Body
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
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
# 前端模版系统
# ==============================

def get_base_layout(content: str, title: str = "Faculty Scraper", active_tab: str = "search", extra_js: str = "") -> str:
    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <link rel="icon" href="/static/favicon.ico" type="image/x-icon">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {{ 
            --primary: #2563eb; --primary-hover: #1d4ed8;
            --bg: #f8fafc; --sidebar-bg: #0f172a; --sidebar-text: #e2e8f0;
            --text: #334155; --danger: #ef4444;
        }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); margin: 0; display: flex; height: 100vh; overflow: hidden; color: var(--text); }}
        
        .sidebar {{ width: 260px; background: var(--sidebar-bg); color: var(--sidebar-text); display: flex; flex-direction: column; padding: 25px; box-shadow: 4px 0 10px rgba(0,0,0,0.05); flex-shrink: 0; }}
        .logo {{ font-size: 1.4rem; font-weight: bold; margin-bottom: 40px; color: white; display: flex; align-items: center; gap: 10px; }}
        .nav-item {{ display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-radius: 8px; cursor: pointer; color: #94a3b8; text-decoration: none; transition: 0.2s; font-size: 0.95rem; margin-bottom: 8px; font-weight: 500; }}
        .nav-item:hover {{ background: #1e293b; color: white; }}
        .nav-item.active {{ background: var(--primary); color: white; box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2); }}
        
        .main-content {{ flex: 1; overflow-y: auto; padding: 40px; position: relative; scroll-behavior: smooth; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        /* 
         * 修复: 增加 white-space: nowrap 和 flex-shrink: 0 
         * 确保按钮文字不换行，按钮不被压缩
         */
        .btn {{ 
            padding: 10px 18px; 
            background: var(--primary); 
            color: white; 
            border: none; 
            border-radius: 6px; 
            cursor: pointer; 
            font-weight: 600; 
            transition: 0.2s; 
            display: inline-flex; 
            align-items: center; 
            gap: 8px; 
            text-decoration: none; 
            font-size: 0.9rem; 
            user-select: none;
            white-space: nowrap; /* 禁止文字换行 */
            flex-shrink: 0;      /* 禁止按钮被压缩 */
        }}
        .btn:hover {{ background: var(--primary-hover); transform: translateY(-1px); }}
        .btn-secondary {{ background: #e2e8f0; color: #475569; }}
        .btn-secondary:hover {{ background: #cbd5e1; }}
        .btn-danger {{ background: #fee2e2; color: #b91c1c; }}
        .btn-danger:hover {{ background: #fecaca; }}

        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 25px; }}
        
        .card {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; display: flex; flex-direction: column; transition: 0.2s; position: relative; }}
        .card:hover {{ transform: translateY(-3px); box-shadow: 0 10px 20px -5px rgba(0,0,0,0.1); border-color: var(--primary); }}
        .card-header {{ padding-bottom: 12px; border-bottom: 1px solid #f1f5f9; margin-bottom: 12px; }}
        .card-title {{ font-size: 1.1rem; font-weight: 700; color: #0f172a; margin: 0; }}
        .card-subtitle {{ font-size: 0.85rem; color: var(--primary); font-weight: 600; margin-top: 4px; display: block; }}
        
        .form-group {{ margin-bottom: 20px; }}
        .form-label {{ display: block; margin-bottom: 8px; font-weight: 600; }}
        .form-input, .form-textarea, .form-select {{ width: 100%; padding: 12px; border: 1px solid #cbd5e1; border-radius: 8px; box-sizing: border-box; outline: none; }}
        .form-input:focus, .form-textarea:focus {{ border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1); }}
        .form-textarea {{ min-height: 120px; resize: vertical; }}
        
        .search-hero {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 25px; display: flex; align-items: center; gap: 15px; border: 1px solid #e2e8f0; }}
        .search-hero i {{ color: var(--text); opacity: 0.5; font-size: 1.1rem; }}
        .search-hero input {{ border: none; flex: 1; font-size: 1rem; outline: none; color: var(--text); }}

        .modal-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(15, 23, 42, 0.6); display: none; align-items: center; justify-content: center; z-index: 1000; backdrop-filter: blur(2px); }}
        .modal {{ background: white; padding: 30px; border-radius: 16px; width: 90%; max-width: 700px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25); display: flex; flex-direction: column; max-height: 90vh; }}
        .modal-body {{ flex: 1; overflow-y: auto; margin: 20px 0; }}
        .modal-body textarea {{ width: 100%; height: 350px; padding: 15px; border: 1px solid #cbd5e1; border-radius: 8px; font-family: monospace; font-size: 0.9rem; }}

        .spinner {{ border: 3px solid #f3f3f3; border-top: 3px solid var(--primary); border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; display: inline-block; }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        
        .toast {{ position: fixed; bottom: 30px; right: 30px; background: #1e293b; color: white; padding: 12px 24px; border-radius: 8px; z-index: 2000; opacity: 0; transition: opacity 0.3s; pointer-events: none; }}
        .toast.show {{ opacity: 1; }}
        .badge {{ background: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; }}
        .no-result {{ text-align: center; padding: 40px; color: #64748b; display: none; grid-column: 1 / -1; }}
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="logo"><i class="fas fa-graduation-cap"></i> Faculty AI</div>
        <a href="/" class="nav-item {'active' if active_tab == 'search' else ''}"><i class="fas fa-search"></i> 院校检索</a>
        <a href="/targets" class="nav-item {'active' if active_tab == 'targets' else ''}"><i class="fas fa-star"></i> 意向导师</a>
        <a href="/profile" class="nav-item {'active' if active_tab == 'profile' else ''}"><i class="fas fa-user-circle"></i> 个人档案</a>
    </div>

    <div class="main-content">
        <div class="container">
            {content}
        </div>
    </div>

    <div class="modal-overlay" id="emailModal">
        <div class="modal">
            <div class="modal-header" style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="margin:0;"><i class="fas fa-envelope-open-text"></i> 生成套磁信</h3>
                <button onclick="closeModal()" style="background:none; border:none; cursor:pointer; font-size:1.5rem; color:#64748b;">&times;</button>
            </div>
            <div class="modal-body">
                <div id="modalLoading" style="text-align:center; padding: 50px; display:none;">
                    <div class="spinner"></div>
                    <p style="margin-top:15px; color:#64748b;">正在分析导师研究方向并结合您的背景撰写邮件...</p>
                </div>
                <div id="modalContent" style="display:none;">
                    <textarea id="emailResult" readonly></textarea>
                </div>
                <div id="modalError" style="color:#ef4444; text-align:center; padding:20px; display:none;"></div>
            </div>
            <div class="modal-footer" style="text-align: right; display: flex; gap: 10px; justify-content: flex-end;">
                <button class="btn btn-secondary" onclick="closeModal()">取消</button>
                <button class="btn" onclick="copyEmail()" id="copyBtn" style="display:none;"><i class="fas fa-copy"></i> 一键复制</button>
            </div>
        </div>
    </div>

    <div id="toast" class="toast">操作成功</div>

    <script>window.profDataMap = {{}};</script>
    {extra_js}

    <script>
        function getTargets() {{ return JSON.parse(localStorage.getItem('faculty_targets') || '[]'); }}
        function saveTargets(data) {{ localStorage.setItem('faculty_targets', JSON.stringify(data)); }}
        function getProfile() {{ return JSON.parse(localStorage.getItem('applicant_profile') || '{{}}'); }}
        function saveProfile(data) {{ localStorage.setItem('applicant_profile', JSON.stringify(data)); }}

        function showToast(msg) {{
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 3000);
        }}

        function addToTargets(idHash, event) {{
            if(event) event.stopPropagation();
            const prof = window.profDataMap[idHash];
            if(!prof) return console.error("Data missing");
            
            const targets = getTargets();
            if (targets.some(t => t.id_hash === prof.id_hash)) {{
                showToast("⚠️ 已在收藏列表中");
                return;
            }}
            targets.push(prof);
            saveTargets(targets);
            showToast("⭐ 已添加");
            
            const btn = document.getElementById('btn-add-' + idHash);
            if(btn) {{
                btn.innerHTML = '<i class="fas fa-check"></i> 已收藏';
                btn.classList.add('btn-secondary');
            }}
        }}

        function removeFromTargets(idHash, event) {{
            if(event) event.stopPropagation();
            let targets = getTargets();
            targets = targets.filter(t => t.id_hash !== idHash);
            saveTargets(targets);
            showToast("🗑️ 已移除");

            if (document.getElementById('targets-grid')) {{
                renderTargets(); 
            }} else {{
                const btn = document.getElementById('btn-add-' + idHash);
                if(btn) {{
                    btn.innerHTML = '<i class="fas fa-star"></i> 收藏';
                    btn.classList.remove('btn-secondary');
                }}
            }}
        }}

        async function openEmailModal(idHash, event) {{
            if(event) event.stopPropagation();
            
            const profile = getProfile();
            if (!profile.name && !profile.university) {{
                if(confirm("⚠️ 您的个人档案为空。是否现在去填写？")) {{
                    window.location.href = "/profile";
                    return;
                }}
            }}

            const prof = window.profDataMap[idHash];
            const modal = document.getElementById('emailModal');
            const loading = document.getElementById('modalLoading');
            const content = document.getElementById('modalContent');
            const errorDiv = document.getElementById('modalError');
            const copyBtn = document.getElementById('copyBtn');
            const textArea = document.getElementById('emailResult');

            modal.style.display = 'flex';
            loading.style.display = 'block';
            content.style.display = 'none';
            errorDiv.style.display = 'none';
            copyBtn.style.display = 'none';
            textArea.value = '';

            try {{
                const response = await fetch('/api/generate-email', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        applicant: profile,
                        professor: prof
                    }})
                }});
                
                if (!response.ok) {{
                    const errText = await response.text();
                    throw new Error("Server Error: " + response.status + " " + errText);
                }}

                const data = await response.json();
                loading.style.display = 'none';
                content.style.display = 'block';
                textArea.value = data.content;
                copyBtn.style.display = 'inline-flex';
                
            }} catch (e) {{
                loading.style.display = 'none';
                errorDiv.style.display = 'block';
                errorDiv.innerText = "❌ " + e.message;
            }}
        }}

        function closeModal() {{ document.getElementById('emailModal').style.display = 'none'; }}
        function copyEmail() {{
            const copyText = document.getElementById("emailResult");
            copyText.select();
            document.execCommand("copy");
            showToast("📋 已复制");
        }}

        function submitProfile(event) {{
            event.preventDefault();
            const formData = new FormData(event.target);
            const profile = Object.fromEntries(formData.entries());
            saveProfile(profile);
            showToast("✅ 档案已保存");
        }}

        document.addEventListener('DOMContentLoaded', () => {{
            if(document.getElementById('profileForm')) {{
                const profile = getProfile();
                const inputs = document.querySelectorAll('#profileForm input, #profileForm textarea, #profileForm select');
                inputs.forEach(input => {{
                    if(profile[input.name]) input.value = profile[input.name];
                }});
            }}
            if(document.getElementById('targets-grid')) {{
                renderTargets();
            }}
        }});

        function renderTargets() {{
            const container = document.getElementById('targets-grid');
            const targets = getTargets();
            
            targets.forEach(p => {{ window.profDataMap[p.id_hash] = p; }});

            if(targets.length === 0) {{
                container.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:50px;color:#94a3b8;"><h3>📭 暂无收藏</h3></div>';
                return;
            }}
            
            container.innerHTML = targets.map(prof => {{
                let areas = prof.research_areas;
                if (Array.isArray(areas)) areas = areas.join(", ");
                
                return `
                <div class="card">
                    <div class="card-header">
                        <div style="display:flex; justify-content:space-between;">
                            <h3 class="card-title">${{prof.name}}</h3>
                            <span class="badge">${{prof.uni_name}}</span>
                        </div>
                        <span class="card-subtitle">${{prof.title}}</span>
                    </div>
                    <div style="flex:1; margin-bottom:15px; font-size:0.9rem; color:#475569;">
                        <p><i class="fas fa-envelope"></i> ${{prof.email}}</p>
                        <p><i class="fas fa-microscope"></i> ${{areas}}</p>
                    </div>
                    <div style="display:flex; gap:10px;">
                        <button class="btn" onclick="openEmailModal('${{prof.id_hash}}', event)" style="flex:1;">
                            <i class="fas fa-magic"></i> 写信
                        </button>
                        <button class="btn btn-secondary btn-danger" onclick="removeFromTargets('${{prof.id_hash}}', event)">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>`;
            }}).join('');
        }}
    </script>
</body>
</html>
    """

# ==============================
# 路由
# ==============================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """首页"""
    unis = get_existing_universities()
    uni_cards = ""
    for u in unis:
        uni_cards += f'''
        <div class="card" style="cursor: pointer;" onclick="location.href='{u['path']}'">
            <div class="card-header"><h3 class="card-title">{u['uni']}</h3></div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; text-align: center; margin-top:10px;">
                <div><strong style="color:var(--primary); font-size:1.2rem;">{u['count']}</strong><div style="font-size:0.75rem;">Faculty</div></div>
                <div><strong style="color:var(--primary); font-size:1.2rem;">{u['titles_count']}</strong><div style="font-size:0.75rem;">Titles</div></div>
                <div><strong style="color:var(--primary); font-size:1.2rem;">{u['areas_count']}</strong><div style="font-size:0.75rem;">Areas</div></div>
            </div>
        </div>'''

    content = f"""
    <div style="background:white; padding:30px; border-radius:12px; margin-bottom:30px;">
        <h2 style="margin-bottom: 20px;">🔍 抓取新院校</h2>
        <!-- 修复: style="flex:1" 允许 input 挤压，同时 btn 不换行 -->
        <form method="POST" action="/scrape" style="display:flex; gap:10px;">
            <input type="text" name="uni" class="form-input" style="flex:1;" placeholder="输入学校名称 (例如: HKU, MIT)" required>
            <button type="submit" class="btn"><i class="fas fa-robot"></i> 开始抓取</button>
        </form>
    </div>
    <h2 style="margin-bottom: 20px;">🏫 已抓取院校</h2>
    <div class="grid">{uni_cards}</div>
    """
    return HTMLResponse(get_base_layout(content))

@app.get("/uni/{uni_name}", response_class=HTMLResponse)
async def uni_detail(uni_name: str):
    """详情页 (增加了搜索功能)"""
    json_path = RUNS_DIR / f"{uni_name}_parsed.json"
    if not json_path.exists(): return RedirectResponse("/")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    faculty_list = []
    js_data_map_lines = []
    
    for idx, prof in enumerate(data.get("faculty", [])):
        prof['uni_name'] = uni_name
        prof['id_hash'] = f"{uni_name}_{idx}"
        
        # 注入 Map
        prof_json = json.dumps(prof)
        js_data_map_lines.append(f"window.profDataMap['{prof['id_hash']}'] = {prof_json};")
        faculty_list.append(prof)

    # 前端筛选逻辑
    extra_js = f"""
    <script>
        {''.join(js_data_map_lines)}
        
        function filterFaculty() {{
            const input = document.getElementById('searchInput').value.toLowerCase();
            const cards = document.getElementsByClassName('search-item');
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
            
            const noRes = document.getElementById('noResult');
            if (visibleCount === 0) {{
                noRes.style.display = 'block';
                noRes.innerHTML = '未找到匹配 "' + document.getElementById('searchInput').value + '" 的导师';
            }} else {{
                noRes.style.display = 'none';
            }}
        }}
    </script>
    """

    cards_html = ""
    for prof in faculty_list:
        areas_display = prof.get('research_areas', [])
        if isinstance(areas_display, list):
            areas_display = ", ".join(areas_display)
        
        # 生成 data-search 属性 (姓名 + 职称 + 领域)
        search_text = f"{prof.get('name', '')} {prof.get('title', '')} {areas_display}".lower()

        cards_html += f'''
        <div class="card search-item" data-search="{search_text}">
            <div class="card-header">
                <h3 class="card-title">{prof.get('name')}</h3>
                <span class="card-subtitle">{prof.get('title')}</span>
            </div>
            <div style="flex:1; margin-bottom:15px; font-size:0.9rem; color:#475569;">
                <p><i class="fas fa-envelope"></i> {prof.get('email')}</p>
                <p><i class="fas fa-microscope"></i> {areas_display}</p>
            </div>
            <div style="display:flex; gap:10px;">
                <button class="btn" id="btn-add-{prof['id_hash']}" onclick="addToTargets('{prof['id_hash']}', event)" style="flex:1;">
                    <i class="fas fa-star"></i> 收藏
                </button>
                <button class="btn btn-secondary" onclick="openEmailModal('{prof['id_hash']}', event)">
                    <i class="fas fa-envelope"></i>
                </button>
            </div>
        </div>
        '''

    content = f"""
    <div>
        <a href="/" style="display:inline-flex; align-items:center; gap:5px; color:#64748b; text-decoration:none; margin-bottom:20px; font-weight:500;"><i class="fas fa-arrow-left"></i> 返回首页</a>
        
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px;">
            <h1 style="margin:0;">{uni_name} Faculty List</h1>
            <span class="badge" style="font-size: 1rem; padding: 8px 15px;">共 {len(faculty_list)} 位</span>
        </div>

        <div class="search-hero">
            <i class="fas fa-search"></i>
            <input type="text" id="searchInput" placeholder="搜索导师姓名、职称或研究方向..." onkeyup="filterFaculty()">
        </div>

        <div class="grid">
            {cards_html}
            <div id="noResult" class="no-result"></div>
        </div>
    </div>
    """
    return HTMLResponse(get_base_layout(content, extra_js=extra_js))

@app.get("/targets", response_class=HTMLResponse)
async def targets_page():
    content = """
    <h1 style="margin-bottom: 30px;">⭐ 意向导师列表</h1>
    <div class="grid" id="targets-grid">
        <div class="spinner"></div> 加载中...
    </div>
    """
    return HTMLResponse(get_base_layout(content, active_tab="targets"))

@app.get("/profile", response_class=HTMLResponse)
async def profile_page():
    content = """
    <h1 style="margin-bottom: 30px;">👤 个人档案</h1>
    <div style="background:white; padding:40px; border-radius:12px; border:1px solid #e2e8f0; max-width:800px;">
        <form id="profileForm" onsubmit="submitProfile(event)">
            <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                <div class="form-group"><label class="form-label">姓名</label><input type="text" name="name" class="form-input" required></div>
                <div class="form-group"><label class="form-label">申请意向</label>
                    <select name="intent" class="form-select">
                        <option value="PhD Application">PhD Application</option>
                        <option value="Master Application">Master Application</option>
                        <option value="Research Intern">Research Intern</option>
                    </select>
                </div>
            </div>
            <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                <div class="form-group"><label class="form-label">院校</label><input type="text" name="university" class="form-input" required></div>
                <div class="form-group"><label class="form-label">专业</label><input type="text" name="major" class="form-input"></div>
            </div>
            <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                <div class="form-group"><label class="form-label">GPA/Ranking</label><input type="text" name="gpa" class="form-input"></div>
                <div class="form-group"><label class="form-label">语言成绩</label><input type="text" name="language_score" class="form-input"></div>
            </div>
            <div class="form-group">
                <label class="form-label">科研经历与亮点</label>
                <textarea name="experience" class="form-textarea" placeholder="简述研究经历，LLM将用于生成套磁信..."></textarea>
            </div>
            <button type="submit" class="btn" style="width:100%; justify-content:center; padding:15px;"><i class="fas fa-save"></i> 保存档案</button>
        </form>
    </div>
    """
    return HTMLResponse(get_base_layout(content, active_tab="profile"))

@app.post("/scrape")
async def run_pipeline(uni: str = Form(...)):
    uni = uni.strip()
    json_path = RUNS_DIR / f"{uni}_parsed.json"
    if json_path.exists(): return RedirectResponse(url=f"/uni/{uni}", status_code=303)

    try:
        planner = PlannerAgent(api_key=LLM_API_KEY)
        uni_info = await planner.normalize_university(uni)
        searcher = SearchAgent(serpapi_key=SEARCH_API_KEY, top_k=5)
        results = await searcher.search_faculty_pages(uni_info["domain"])
        if not results: raise Exception("No faculty page found")
        
        md_path = RUNS_DIR / f"{uni}.md"
        async with CrawlerAgent() as crawler:
            await crawler.crawl_faculty(results[0]['url'], save_md=True, md_path=str(md_path))
        
        with open(md_path, 'r', encoding='utf-8') as f: content = f.read()
        parser = ParserAgent(api_key=LLM_API_KEY)
        parsed = parser.parse(content)
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        return RedirectResponse(url=f"/uni/{uni}", status_code=303)
    except Exception as e:
        logger.error(e)
        return HTMLResponse(get_base_layout(f"<h3>❌ Error</h3><p>{e}</p>"))

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